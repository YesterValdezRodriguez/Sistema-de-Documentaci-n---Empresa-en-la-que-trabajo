/* Armador de Expedientes — Motor de PDF (pdf-lib)
 *
 * Une las páginas de varios PDF en el orden de una plantilla y aplica una capa
 * de sellos/foliado. Funciona 100 % en el navegador (no envía nada a ningún
 * servidor). También se puede cargar en Node para pruebas.
 */
(function (global) {
  'use strict';

  function getPDFLib() {
    if (global.PDFLib) return global.PDFLib;
    if (typeof require !== 'undefined') return require('../vendor/pdf-lib.min.js');
    throw new Error('pdf-lib no está disponible');
  }

  // ---- Rango de páginas: "1-3,5,8-" -> índices base 0 ----
  function parseRango(rango, total) {
    if (total <= 0) return [];
    if (!rango || !String(rango).trim()) {
      const todas = [];
      for (let i = 0; i < total; i++) todas.push(i);
      return todas;
    }
    const indices = [];
    String(rango).split(',').forEach(function (parte) {
      parte = parte.trim();
      if (!parte) return;
      if (parte.indexOf('-') >= 0) {
        const trozos = parte.split('-');
        let ini = trozos[0].trim() === '' ? 1 : parseInt(trozos[0], 10);
        let fin = trozos[1].trim() === '' ? total : parseInt(trozos[1], 10);
        if (isNaN(ini) || isNaN(fin)) return;
        if (ini > fin) { const t = ini; ini = fin; fin = t; }
        for (let n = ini; n <= fin; n++) if (n >= 1 && n <= total) indices.push(n - 1);
      } else {
        const n = parseInt(parte, 10);
        if (!isNaN(n) && n >= 1 && n <= total) indices.push(n - 1);
      }
    });
    return indices;
  }

  // ---- Validación sintáctica del rango (null = ok) ----
  function validarRango(rango) {
    if (!rango || !String(rango).trim()) return null;
    const partes = String(rango).split(',');
    for (let i = 0; i < partes.length; i++) {
      const parte = partes[i].trim();
      if (!parte) continue;
      if (!/^\d*-?\d*$/.test(parte) || parte === '-') {
        return 'Rango de páginas inválido: «' + parte + '»';
      }
    }
    return null;
  }

  function contarPaginas(bytes) {
    const { PDFDocument } = getPDFLib();
    return PDFDocument.load(bytes, { ignoreEncryption: true })
      .then(function (d) { return d.getPageCount(); })
      .catch(function () { return 0; });
  }

  function esPdfValido(bytes) {
    const { PDFDocument } = getPDFLib();
    return PDFDocument.load(bytes, { ignoreEncryption: true })
      .then(function (d) { return d.getPageCount() > 0; })
      .catch(function () { return false; });
  }

  function formatear(plantillaTexto, ctx) {
    if (!plantillaTexto) return '';
    return String(plantillaTexto).replace(/\{(\w+)\}/g, function (m, clave) {
      return (ctx[clave] !== undefined && ctx[clave] !== null) ? String(ctx[clave]) : m;
    });
  }

  function dibujarTexto(page, font, texto, posicion, tam, color, w, h) {
    if (!texto) return;
    const margen = 20;
    let ancho = 0;
    try { ancho = font.widthOfTextAtSize(texto, tam); } catch (e) { ancho = texto.length * tam * 0.5; }
    let x;
    if (/IZQ$/.test(posicion)) x = margen;
    else if (/DER$/.test(posicion)) x = w - margen - ancho;
    else x = (w - ancho) / 2;            // CEN
    const y = /^SUP/.test(posicion) ? (h - margen - tam) : margen;
    try {
      page.drawText(texto, { x: x, y: y, size: tam, font: font, color: color });
    } catch (e) { /* carácter no soportado por la fuente: se omite */ }
  }

  function aplicarSellos(page, font, plantilla, meta, ctx) {
    const { rgb } = getPDFLib();
    const tam = page.getSize();
    const w = tam.width, h = tam.height;
    const s = plantilla.sellos || {};
    const azul = rgb(0.106, 0.227, 0.42);
    const rojo = rgb(0.75, 0.22, 0.17);
    const negro = rgb(0, 0, 0);

    if (s.mostrarEncabezado && s.formatoEncabezado)
      dibujarTexto(page, font, formatear(s.formatoEncabezado, ctx), s.posicionEncabezado || 'SUP_CEN', 8, azul, w, h);
    if (s.textoSello)
      dibujarTexto(page, font, formatear(s.textoSello, ctx), s.posicionSello || 'SUP_DER', 10, rojo, w, h);
    if (meta && meta.sellarPaso && meta.paso)
      dibujarTexto(page, font, 'PASO: ' + meta.paso, 'SUP_IZQ', 9, azul, w, h);
    if (s.foliar && s.formatoFolio)
      dibujarTexto(page, font, formatear(s.formatoFolio, ctx), s.posicionFolio || 'INF_DER', 8, negro, w, h);
  }

  /**
   * Ensambla el expediente.
   *
   * Cada ítem aporta sus páginas (según su rango) y, además, puede llevar
   * **inserciones**: PDFs que se intercalan *entre* las páginas de ese ítem
   * (p. ej. un registro de limpieza que va después de la página 3 de la
   * fórmula maestra). Cada inserción indica `despuesDePagina` (0 = al inicio;
   * un número mayor que el total = al final).
   *
   * @param {Object} plantilla  - { items:[ { ..., inserciones:[...] } ], sellos:{...} }
   * @param {Function} obtenerBytes - async (ref) => ArrayBuffer|Uint8Array|null
   * @param {Object} contexto   - { producto, lote, codigo, fecha, version }
   * @returns {Promise<Uint8Array|null>} bytes del PDF (null si no hay páginas)
   */
  async function ensamblar(plantilla, obtenerBytes, contexto) {
    const { PDFDocument, StandardFonts } = getPDFLib();
    const ctx = contexto || {};
    const items = (plantilla.items || []).slice().sort(function (a, b) {
      return (a.orden || 0) - (b.orden || 0);
    });

    const salida = await PDFDocument.create();
    const font = await salida.embedFont(StandardFonts.HelveticaBold);
    const metaPaginas = [];

    // Emite las páginas de una referencia (ítem o inserción) al final del PDF.
    async function emitirRef(ref) {
      let bytes;
      try { bytes = await obtenerBytes(ref); } catch (e) { bytes = null; }
      if (!bytes) return 0;
      let doc;
      try { doc = await PDFDocument.load(bytes, { ignoreEncryption: true }); } catch (e) { return 0; }
      const indices = parseRango(ref.rangoPaginas, doc.getPageCount());
      if (!indices.length) return 0;
      let copiadas;
      try { copiadas = await salida.copyPages(doc, indices); } catch (e) { return 0; }
      copiadas.forEach(function (pg) {
        salida.addPage(pg);
        metaPaginas.push({ paso: ref.paso || '', sellarPaso: !!ref.sellarPaso });
      });
      return copiadas.length;
    }

    for (let k = 0; k < items.length; k++) {
      const item = items[k];
      const inserciones = (item.inserciones || []).slice().sort(function (a, b) {
        return (a.despuesDePagina || 0) - (b.despuesDePagina || 0);
      });

      // Páginas base del ítem
      let baseDoc = null, baseIndices = [];
      let baseBytes;
      try { baseBytes = await obtenerBytes(item); } catch (e) { baseBytes = null; }
      if (baseBytes) {
        try { baseDoc = await PDFDocument.load(baseBytes, { ignoreEncryption: true }); } catch (e) { baseDoc = null; }
        if (baseDoc) baseIndices = parseRango(item.rangoPaginas, baseDoc.getPageCount());
      }
      let baseCopiadas = [];
      if (baseDoc && baseIndices.length) {
        try { baseCopiadas = await salida.copyPages(baseDoc, baseIndices); } catch (e) { baseCopiadas = []; }
      }

      // Inserciones antes de la primera página (despuesDePagina <= 0)
      for (let i = 0; i < inserciones.length; i++) {
        if ((inserciones[i].despuesDePagina || 0) <= 0) await emitirRef(inserciones[i]);
      }
      // Páginas base, intercalando las inserciones después de cada posición
      for (let pos = 1; pos <= baseCopiadas.length; pos++) {
        salida.addPage(baseCopiadas[pos - 1]);
        metaPaginas.push({ paso: item.paso || '', sellarPaso: !!item.sellarPaso });
        for (let i = 0; i < inserciones.length; i++) {
          if ((inserciones[i].despuesDePagina || 0) === pos) await emitirRef(inserciones[i]);
        }
      }
      // Inserciones más allá del final del ítem (o si el ítem no tiene base)
      for (let i = 0; i < inserciones.length; i++) {
        if ((inserciones[i].despuesDePagina || 0) > baseCopiadas.length) await emitirRef(inserciones[i]);
      }
    }

    const paginas = salida.getPages();
    if (!paginas.length) return null;

    const totalP = paginas.length;
    for (let i = 0; i < paginas.length; i++) {
      const ctxPg = Object.assign({}, ctx, {
        pagina: i + 1, total: totalP, paso: (metaPaginas[i] && metaPaginas[i].paso) || ''
      });
      aplicarSellos(paginas[i], font, plantilla, metaPaginas[i], ctxPg);
    }
    return await salida.save();
  }

  async function pdfMensaje(texto) {
    const { PDFDocument, StandardFonts, rgb } = getPDFLib();
    const d = await PDFDocument.create();
    const font = await d.embedFont(StandardFonts.HelveticaBold);
    const page = d.addPage([612, 792]);
    const linea = String(texto || '').slice(0, 90);
    const tam = 13;
    const ancho = font.widthOfTextAtSize(linea, tam);
    page.drawText(linea, { x: (612 - ancho) / 2, y: 430, size: tam, font: font, color: rgb(0.106, 0.227, 0.42) });
    return await d.save();
  }

  const api = {
    parseRango: parseRango,
    validarRango: validarRango,
    contarPaginas: contarPaginas,
    esPdfValido: esPdfValido,
    ensamblar: ensamblar,
    pdfMensaje: pdfMensaje,
    formatear: formatear
  };

  global.MotorPDF = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
