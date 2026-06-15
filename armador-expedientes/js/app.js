/* Armador de Expedientes — Lógica de la aplicación (sin servidor) */
(function () {
  'use strict';

  // -------------------------------------------------- catálogos
  const TIPOS = {
    MAESTRA: 'Fórmula Maestra / Batch Record',
    REGISTRO: 'Registro / Formato',
    ANEXO: 'Anexo / Instructivo',
    OTRO: 'Otro documento'
  };
  const POSICIONES = {
    SUP_IZQ: 'Superior izquierda', SUP_CEN: 'Superior centro', SUP_DER: 'Superior derecha',
    INF_IZQ: 'Inferior izquierda', INF_CEN: 'Inferior centro', INF_DER: 'Inferior derecha'
  };
  function sellosPorDefecto() {
    return {
      foliar: true, formatoFolio: 'Hoja {pagina} de {total}', posicionFolio: 'INF_DER',
      mostrarEncabezado: false, formatoEncabezado: '{producto}  |  Lote: {lote}', posicionEncabezado: 'SUP_CEN',
      textoSello: '', posicionSello: 'SUP_DER'
    };
  }

  // -------------------------------------------------- utilidades
  const app = document.getElementById('app');
  function uid() {
    return (window.crypto && crypto.randomUUID) ? crypto.randomUUID()
      : 'id-' + Date.now() + '-' + Math.random().toString(16).slice(2);
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function hoyISO() { return new Date().toISOString().slice(0, 10); }
  function fmtFecha(iso) {
    if (!iso) return '—';
    const p = String(iso).slice(0, 10).split('-');
    return p.length === 3 ? (p[2] + '/' + p[1] + '/' + p[0]) : iso;
  }
  function fmtFechaHora(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    const z = function (n) { return ('0' + n).slice(-2); };
    return z(d.getDate()) + '/' + z(d.getMonth() + 1) + '/' + d.getFullYear() + ' ' + z(d.getHours()) + ':' + z(d.getMinutes());
  }
  function tamanoLegible(n) {
    if (!n) return '—';
    const u = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return (i === 0 ? n : n.toFixed(1)) + ' ' + u[i];
  }
  function slug(t) {
    return (String(t || '').trim().replace(/[^\w\-. ]+/g, '').replace(/\s+/g, '_')) || 'expediente';
  }
  function descargar(nombre, contenido, tipo) {
    const blob = (contenido instanceof Blob) ? contenido : new Blob([contenido], { type: tipo || 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = nombre; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1500);
  }
  function toast(msg, tipo) {
    const cont = document.getElementById('toasts');
    const t = document.createElement('div');
    t.className = 'toast ' + (tipo || 'ok');
    t.textContent = msg;
    cont.appendChild(t);
    setTimeout(function () { t.classList.add('mostrar'); }, 10);
    setTimeout(function () { t.classList.remove('mostrar'); setTimeout(function () { t.remove(); }, 300); }, 4200);
  }
  function confirmar(msg) { return window.confirm(msg); }

  function modal(titulo, cuerpoHTML, botones, opciones) {
    opciones = opciones || {};
    const dlg = document.createElement('dialog');
    dlg.className = 'modal' + (opciones.ancho ? ' modal-xl' : '');
    dlg.innerHTML =
      '<div class="modal-head"><h3>' + esc(titulo) + '</h3>' +
      '<button class="x" type="button" aria-label="Cerrar">&times;</button></div>' +
      '<div class="modal-body">' + cuerpoHTML + '</div>' +
      '<div class="modal-foot"></div>';
    const foot = dlg.querySelector('.modal-foot');
    (botones || []).forEach(function (b) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn ' + (b.clase || 'sec');
      btn.innerHTML = b.texto;
      btn.onclick = function () { b.onClick(dlg); };
      foot.appendChild(btn);
    });
    dlg.querySelector('.x').onclick = function () { dlg.close(); };
    document.body.appendChild(dlg);
    dlg.addEventListener('close', function () {
      if (opciones.alCerrar) opciones.alCerrar();
      dlg.remove();
    });
    dlg.showModal();
    return dlg;
  }

  function leerBytes(file) { return file.arrayBuffer(); }

  // -------------------------------------------------- datos derivados
  async function archivosPorId() {
    const arr = await DB.getAll('archivos');
    const m = {};
    arr.forEach(function (a) { m[a.id] = a; });
    return { lista: arr, mapa: m };
  }
  function versionActual(archivo) {
    if (!archivo || !archivo.versiones || !archivo.versiones.length) return null;
    if (archivo.versionActualId) {
      const v = archivo.versiones.find(function (x) { return x.id === archivo.versionActualId; });
      if (v) return v;
    }
    return archivo.versiones[archivo.versiones.length - 1];
  }
  function versionEfectivaMeta(archivo, item) {
    if (!archivo) return null;
    if (!item.usarVersionActual && item.versionFijaId) {
      const v = (archivo.versiones || []).find(function (x) { return x.id === item.versionFijaId; });
      if (v) return v;
    }
    return versionActual(archivo);
  }
  function paginasItem(item, mapa) {
    const v = versionEfectivaMeta(mapa[item.archivoId], item);
    if (!v) return 0;
    return MotorPDF.parseRango(item.rangoPaginas, v.numPaginas || 0).length;
  }
  function paginasItemConInserciones(item, mapa) {
    let n = paginasItem(item, mapa);
    (item.inserciones || []).forEach(function (ins) { n += paginasItem(ins, mapa); });
    return n;
  }
  function totalPaginas(plantilla, mapa) {
    return (plantilla.items || []).reduce(function (s, it) { return s + paginasItemConInserciones(it, mapa); }, 0);
  }
  function obtenerBytesFactory(mapa) {
    return async function (item) {
      const a = mapa[item.archivoId];
      const v = versionEfectivaMeta(a, item);
      if (!v) return null;
      return await DB.getBlob(v.id);
    };
  }

  function mostrarError(e) {
    console.error(e);
    app.innerHTML = '<div class="card"><p class="peligro">Ocurrió un error: ' + esc(e.message || e) + '</p></div>';
  }

  // Serializa las mutaciones de una plantilla para que operaciones rápidas
  // (lectura-modificación-escritura) no se pisen y pierdan cambios.
  let _cola = Promise.resolve();
  function serial(tarea) {
    const r = _cola.then(tarea, tarea);
    _cola = r.then(function () { }, function () { });
    return r;
  }
  function mutarPlantilla(id, fn) {
    return serial(async function () {
      const p = await DB.get('plantillas', id);
      if (!p) return null;
      await fn(p);
      p.modificado = new Date().toISOString();
      await DB.put('plantillas', p);
      return p;
    });
  }

  // ==================================================================
  //  VISTA: PLANTILLAS (inicio)
  // ==================================================================
  async function renderPlantillas() {
    const plantillas = await DB.getAll('plantillas');
    const { mapa } = await archivosPorId();
    plantillas.sort(function (a, b) { return (a.nombre || '').localeCompare(b.nombre || ''); });

    let filas = plantillas.map(function (p) {
      return '<tr>' +
        '<td><a href="#/plantilla/' + p.id + '" class="enlace fuerte">' + esc(p.nombre) + '</a></td>' +
        '<td>' + esc(p.producto || '—') + '</td>' +
        '<td>' + esc(p.codigo || '—') + '</td>' +
        '<td class="centro">' + (p.items ? p.items.length : 0) + '</td>' +
        '<td class="centro">' + totalPaginas(p, mapa) + '</td>' +
        '<td class="der">' +
          '<a class="btn mini prim" href="#/plantilla/' + p.id + '" title="Abrir / armar">✎</a> ' +
          '<button class="btn mini ok" data-generar="' + p.id + '" title="Generar expediente">▶</button> ' +
          '<button class="btn mini pel" data-del="' + p.id + '" title="Eliminar">🗑</button>' +
        '</td></tr>';
    }).join('');
    if (!plantillas.length) filas = '<tr><td colspan="6" class="centro muted pad">No hay plantillas todavía. Cree la primera.</td></tr>';

    app.innerHTML =
      '<div class="aviso"><b>Plantilla</b> = la configuración de un expediente (batch record): qué registros lo ' +
      'componen, en qué orden y en qué paso van. Ármela una vez y reutilícela en cada lote.</div>' +
      '<div class="barra"><h2>Plantillas de expedientes</h2>' +
      '<button class="btn prim" id="btnNueva">+ Nueva plantilla</button></div>' +
      '<div class="card sinpad"><table class="tabla"><thead><tr>' +
      '<th>Nombre</th><th>Producto</th><th>Código</th><th class="centro">Registros</th>' +
      '<th class="centro">Págs.</th><th></th></tr></thead><tbody>' + filas + '</tbody></table></div>';

    document.getElementById('btnNueva').onclick = dialogoNuevaPlantilla;
    app.querySelectorAll('[data-del]').forEach(function (b) {
      b.onclick = function () { eliminarPlantilla(b.getAttribute('data-del')); };
    });
    app.querySelectorAll('[data-generar]').forEach(function (b) {
      b.onclick = function () { dialogoGenerar(b.getAttribute('data-generar')); };
    });
  }

  function dialogoNuevaPlantilla() {
    const cuerpo =
      '<div class="grid">' +
      '<label class="c8">Nombre *<input id="np_nombre" placeholder="Ej. Expediente de fabricación — Paracetamol 500 mg"></label>' +
      '<label class="c4">Versión<input id="np_version" value="01"></label>' +
      '<label class="c7">Producto<input id="np_producto" placeholder="Producto farmacéutico"></label>' +
      '<label class="c5">Código<input id="np_codigo" placeholder="Ej. BR-PAR-500"></label>' +
      '<label class="c12">Descripción<textarea id="np_desc" rows="2"></textarea></label>' +
      '</div>';
    modal('Nueva plantilla', cuerpo, [
      { texto: 'Cancelar', clase: 'sec', onClick: function (d) { d.close(); } },
      {
        texto: 'Crear y armar', clase: 'prim', onClick: async function (d) {
          const nombre = d.querySelector('#np_nombre').value.trim();
          if (!nombre) { toast('El nombre es obligatorio.', 'pel'); return; }
          const p = {
            id: uid(), nombre: nombre,
            producto: d.querySelector('#np_producto').value.trim(),
            codigo: d.querySelector('#np_codigo').value.trim(),
            version: d.querySelector('#np_version').value.trim() || '01',
            descripcion: d.querySelector('#np_desc').value.trim(),
            sellos: sellosPorDefecto(), items: [],
            creado: new Date().toISOString(), modificado: new Date().toISOString()
          };
          await DB.put('plantillas', p);
          d.close();
          location.hash = '#/plantilla/' + p.id;
        }
      }
    ]);
  }

  async function eliminarPlantilla(id) {
    if (!confirmar('¿Eliminar esta plantilla? Su estructura se borrará (los expedientes ya armados se conservan).')) return;
    await DB.del('plantillas', id);
    toast('Plantilla eliminada.');
    renderPlantillas();
  }

  // ==================================================================
  //  VISTA: BUILDER (armado interactivo)
  // ==================================================================
  async function renderBuilder(id) {
    const plantilla = await DB.get('plantillas', id);
    if (!plantilla) { app.innerHTML = '<div class="card">Plantilla no encontrada.</div>'; return; }
    const { lista, mapa } = await archivosPorId();
    plantilla.items = (plantilla.items || []).slice().sort(function (a, b) { return (a.orden || 0) - (b.orden || 0); });
    const s = plantilla.sellos || sellosPorDefecto();

    const itemsHTML = plantilla.items.map(function (it, idx) {
      const a = mapa[it.archivoId];
      const v = versionEfectivaMeta(a, it);
      const inserciones = (it.inserciones || []).slice().sort(function (x, y) { return (x.despuesDePagina || 0) - (y.despuesDePagina || 0); });
      const insHTML = inserciones.map(function (ins) {
        const ia = mapa[ins.archivoId];
        const dp = ins.despuesDePagina || 0;
        const pos = dp <= 0 ? 'al inicio' : ('después de pág. ' + dp);
        return '<div class="insercion">' +
          '<span class="flecha">⤵</span>' +
          '<div class="ins-info"><span class="fuerte">' + esc(ia ? ia.nombre : '(archivo eliminado)') + '</span> ' +
          '<span class="muted">— ' + pos + ' · ' + (ins.rangoPaginas ? ('págs. ' + esc(ins.rangoPaginas)) : 'todas') +
          ' (' + paginasItem(ins, mapa) + ')' + (ins.paso ? (' · ' + esc(ins.paso) + (ins.sellarPaso ? ' 🔖' : '')) : '') + '</span></div>' +
          '<button class="btn mini prim" data-edit-ins="' + ins.id + '" data-item="' + it.id + '" title="Editar inserción">✎</button>' +
          '<button class="btn mini pel" data-quita-ins="' + ins.id + '" data-item="' + it.id + '" title="Quitar inserción">✕</button>' +
          '</div>';
      }).join('');
      const insBloque = inserciones.length ? ('<div class="inserciones">' + insHTML + '</div>') : '';
      return '<div class="item" draggable="true" data-id="' + it.id + '">' +
        '<div class="item-fila">' +
          '<span class="grip" title="Arrastrar">⋮⋮</span>' +
          '<span class="orden">' + (idx + 1) + '</span>' +
          '<div class="item-info"><div class="fuerte">' + esc(a ? a.nombre : '(archivo eliminado)') +
            (a ? ' <span class="chip">' + esc(TIPOS[a.tipo] || a.tipo) + '</span>' : '') + '</div>' +
          '<div class="muted small">' +
            '↳ ' + (v ? ('v' + esc(v.numero) + (it.usarVersionActual ? ' (actual)' : ' (fija)')) : 'sin versión') + ' · ' +
            (it.rangoPaginas ? ('págs. ' + esc(it.rangoPaginas)) : 'todas las págs.') + ' (' + paginasItem(it, mapa) + ') · ' +
            (it.paso ? ('paso: ' + esc(it.paso) + (it.sellarPaso ? ' 🔖' : '')) : '<i>sin paso</i>') +
          '</div>' + (it.titulo ? '<div class="small">' + esc(it.titulo) + '</div>' : '') + '</div>' +
          '<div class="item-btns">' +
            '<button class="btn mini" data-grafico="' + it.id + '" title="Insertar gráficamente (ver páginas)">🖼</button>' +
            '<button class="btn mini" data-ins="' + it.id + '" title="Insertar PDF entre páginas">⤵</button>' +
            '<button class="btn mini" data-sube="' + it.id + '" ' + (idx === 0 ? 'disabled' : '') + ' title="Subir">▲</button>' +
            '<button class="btn mini" data-baja="' + it.id + '" ' + (idx === plantilla.items.length - 1 ? 'disabled' : '') + ' title="Bajar">▼</button>' +
            '<button class="btn mini prim" data-edit="' + it.id + '" title="Editar">✎</button>' +
            '<button class="btn mini pel" data-quita="' + it.id + '" title="Quitar">✕</button>' +
          '</div>' +
        '</div>' + insBloque + '</div>';
    }).join('') || '<p class="centro muted pad">Aún no hay registros. Agregue el primero abajo.</p>';

    const opcArchivos = lista.map(function (a) {
      return '<option value="' + a.id + '">' + esc((a.codigo ? a.codigo + ' — ' : '') + a.nombre) +
        ' (' + esc(TIPOS[a.tipo] || a.tipo) + ', ' + (versionActual(a) ? versionActual(a).numPaginas : 0) + ' pág.)</option>';
    }).join('');

    const selPos = function (name, val) {
      return '<select id="' + name + '">' + Object.keys(POSICIONES).map(function (k) {
        return '<option value="' + k + '"' + (val === k ? ' selected' : '') + '>' + POSICIONES[k] + '</option>';
      }).join('') + '</select>';
    };

    const formAgregar = lista.length ?
      ('<div class="card-foot"><div class="grid">' +
        '<label class="c12">Registro / PDF a insertar<select id="ag_archivo"><option value="">— Elegir —</option>' + opcArchivos + '</select></label>' +
        '<label class="c3">Páginas<input id="ag_rango" placeholder="todas"></label>' +
        '<label class="c5">Paso / etapa<input id="ag_paso" placeholder="Ej. Pesada"></label>' +
        '<label class="c4 check"><input type="checkbox" id="ag_sellar"> Sellar paso</label>' +
        '<label class="c12">Descripción (opcional)<input id="ag_titulo"></label>' +
        '<div class="c12"><button class="btn prim" id="btnAgregar">+ Agregar registro</button></div>' +
        '</div><div class="small muted">Páginas: vacío = todas. Ej. <code>1-3</code>, <code>2,5</code>, <code>4-</code>. ' +
        '¿Falta un PDF? <a class="enlace" href="#/archivos">Cárguelo en Registros/PDFs</a>.</div></div>')
      : '<div class="card-foot"><div class="aviso pel">No hay PDFs cargados. <a class="enlace" href="#/archivos">Cargue un PDF</a> para poder armar el expediente.</div></div>';

    app.innerHTML =
      '<div class="barra"><div><a href="#/plantillas" class="enlace small">‹ Plantillas</a>' +
      '<h2>' + esc(plantilla.nombre) + '</h2>' +
      '<div class="chips">' + (plantilla.producto ? '<span class="chip">' + esc(plantilla.producto) + '</span>' : '') +
        (plantilla.codigo ? '<span class="chip">' + esc(plantilla.codigo) + '</span>' : '') +
        '<span class="chip">v' + esc(plantilla.version) + '</span>' +
        '<span class="chip prim">' + plantilla.items.length + ' registro(s)</span>' +
        '<span class="chip">' + totalPaginas(plantilla, mapa) + ' pág.</span></div></div>' +
      '<div class="acciones">' +
        '<button class="btn" id="btnPreview">👁 Vista previa</button>' +
        '<button class="btn ok" id="btnGenerar">▶ Generar expediente</button>' +
        '<button class="btn sec" id="btnDuplicar">⧉ Guardar como nueva config.</button>' +
      '</div></div>' +
      '<div class="cols">' +
        '<div class="col-izq"><div class="card sinpad">' +
          '<div class="card-head">Estructura del expediente <span class="muted small">— arrastre para reordenar</span></div>' +
          '<div class="lista-items" id="listaItems">' + itemsHTML + '</div>' + formAgregar + '</div></div>' +
        '<div class="col-der">' +
          '<div class="card"><div class="card-head">Datos de la plantilla</div><div class="grid">' +
            '<label class="c8">Nombre *<input id="pl_nombre" value="' + esc(plantilla.nombre) + '"></label>' +
            '<label class="c4">Versión<input id="pl_version" value="' + esc(plantilla.version) + '"></label>' +
            '<label class="c7">Producto<input id="pl_producto" value="' + esc(plantilla.producto || '') + '"></label>' +
            '<label class="c5">Código<input id="pl_codigo" value="' + esc(plantilla.codigo || '') + '"></label>' +
            '<label class="c12">Descripción<textarea id="pl_desc" rows="2">' + esc(plantilla.descripcion || '') + '</textarea></label>' +
            '<div class="c12"><button class="btn prim" id="btnGuardarDatos">Guardar datos</button></div></div></div>' +
          '<div class="card"><div class="card-head">Sellado y foliado de las hojas</div><div class="grid">' +
            '<label class="c12 check"><input type="checkbox" id="se_foliar"' + (s.foliar ? ' checked' : '') + '> Foliar (numerar hojas)</label>' +
            '<label class="c7">Formato folio<input id="se_ffolio" value="' + esc(s.formatoFolio || '') + '"></label>' +
            '<label class="c5">Posición' + selPos('se_pfolio', s.posicionFolio) + '</label>' +
            '<label class="c12 check"><input type="checkbox" id="se_enc"' + (s.mostrarEncabezado ? ' checked' : '') + '> Encabezado en cada hoja</label>' +
            '<label class="c7">Formato encabezado<input id="se_fenc" value="' + esc(s.formatoEncabezado || '') + '"></label>' +
            '<label class="c5">Posición' + selPos('se_penc', s.posicionEncabezado) + '</label>' +
            '<label class="c7">Sello (texto)<input id="se_sello" value="' + esc(s.textoSello || '') + '" placeholder="Ej. ORIGINAL"></label>' +
            '<label class="c5">Posición' + selPos('se_psello', s.posicionSello) + '</label>' +
            '<div class="c12 small muted">Marcadores: <code>{producto}</code> <code>{lote}</code> <code>{codigo}</code> ' +
              '<code>{fecha}</code> <code>{pagina}</code> <code>{total}</code> <code>{version}</code></div>' +
            '<div class="c12"><button class="btn prim" id="btnGuardarSellos">Guardar sellado</button></div></div></div>' +
        '</div></div>';

    // ---- eventos ----
    document.getElementById('btnPreview').onclick = function () { previsualizar(plantilla.id); };
    document.getElementById('btnGenerar').onclick = function () { dialogoGenerar(plantilla.id); };
    document.getElementById('btnDuplicar').onclick = function () { dialogoDuplicar(plantilla); };
    document.getElementById('btnGuardarDatos').onclick = function () { guardarDatos(plantilla.id); };
    document.getElementById('btnGuardarSellos').onclick = function () { guardarSellos(plantilla.id); };
    if (document.getElementById('btnAgregar')) document.getElementById('btnAgregar').onclick = function () { agregarItem(plantilla.id); };

    app.querySelectorAll('[data-sube]').forEach(function (b) { b.onclick = function () { moverItem(plantilla.id, b.getAttribute('data-sube'), -1); }; });
    app.querySelectorAll('[data-baja]').forEach(function (b) { b.onclick = function () { moverItem(plantilla.id, b.getAttribute('data-baja'), 1); }; });
    app.querySelectorAll('[data-quita]').forEach(function (b) { b.onclick = function () { quitarItem(plantilla.id, b.getAttribute('data-quita')); }; });
    app.querySelectorAll('[data-edit]').forEach(function (b) { b.onclick = function () { dialogoEditarItem(plantilla.id, b.getAttribute('data-edit')); }; });
    app.querySelectorAll('[data-grafico]').forEach(function (b) { b.onclick = function () { location.hash = '#/grafico/' + plantilla.id + '/' + b.getAttribute('data-grafico'); }; });
    app.querySelectorAll('[data-ins]').forEach(function (b) { b.onclick = function () { dialogoInsercion(plantilla.id, b.getAttribute('data-ins'), null); }; });
    app.querySelectorAll('[data-edit-ins]').forEach(function (b) { b.onclick = function () { dialogoInsercion(plantilla.id, b.getAttribute('data-item'), b.getAttribute('data-edit-ins')); }; });
    app.querySelectorAll('[data-quita-ins]').forEach(function (b) { b.onclick = function () { quitarInsercion(plantilla.id, b.getAttribute('data-item'), b.getAttribute('data-quita-ins')); }; });

    activarArrastre(plantilla.id);
  }

  function activarArrastre(plantillaId) {
    const lista = document.getElementById('listaItems');
    if (!lista) return;
    let arrastrando = null;
    lista.querySelectorAll('.item').forEach(function (row) {
      row.addEventListener('dragstart', function () { arrastrando = row; row.classList.add('arrastre'); });
      row.addEventListener('dragend', function () {
        row.classList.remove('arrastre'); arrastrando = null; guardarOrden(plantillaId);
      });
    });
    lista.addEventListener('dragover', function (e) {
      e.preventDefault();
      const drag = lista.querySelector('.arrastre');
      if (!drag) return;
      const despues = elementoDespuesDe(lista, e.clientY);
      if (despues == null) lista.appendChild(drag);
      else lista.insertBefore(drag, despues);
    });
  }
  function elementoDespuesDe(cont, y) {
    const items = Array.prototype.slice.call(cont.querySelectorAll('.item:not(.arrastre)'));
    let mejor = { offset: Number.NEGATIVE_INFINITY, el: null };
    items.forEach(function (child) {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > mejor.offset) mejor = { offset: offset, el: child };
    });
    return mejor.el;
  }
  async function guardarOrden(plantillaId) {
    const lista = document.getElementById('listaItems');
    const ids = Array.prototype.slice.call(lista.querySelectorAll('.item')).map(function (r) { return r.getAttribute('data-id'); });
    await mutarPlantilla(plantillaId, function (p) {
      const mapaItem = {}; (p.items || []).forEach(function (it) { mapaItem[it.id] = it; });
      p.items = ids.map(function (id, i) { const it = mapaItem[id]; if (it) it.orden = i; return it; }).filter(Boolean);
    });
    renderBuilder(plantillaId);
  }

  async function guardarDatos(id) {
    const nombre = document.getElementById('pl_nombre').value.trim();
    if (!nombre) { toast('El nombre es obligatorio.', 'pel'); return; }
    const datos = {
      nombre: nombre,
      version: document.getElementById('pl_version').value.trim() || '01',
      producto: document.getElementById('pl_producto').value.trim(),
      codigo: document.getElementById('pl_codigo').value.trim(),
      descripcion: document.getElementById('pl_desc').value.trim()
    };
    await mutarPlantilla(id, function (p) {
      p.nombre = datos.nombre; p.version = datos.version; p.producto = datos.producto;
      p.codigo = datos.codigo; p.descripcion = datos.descripcion;
    });
    toast('Datos guardados.');
    renderBuilder(id);
  }
  async function guardarSellos(id) {
    const sellos = {
      foliar: document.getElementById('se_foliar').checked,
      formatoFolio: document.getElementById('se_ffolio').value.trim(),
      posicionFolio: document.getElementById('se_pfolio').value,
      mostrarEncabezado: document.getElementById('se_enc').checked,
      formatoEncabezado: document.getElementById('se_fenc').value.trim(),
      posicionEncabezado: document.getElementById('se_penc').value,
      textoSello: document.getElementById('se_sello').value.trim(),
      posicionSello: document.getElementById('se_psello').value
    };
    await mutarPlantilla(id, function (p) { p.sellos = sellos; });
    toast('Sellado guardado.');
  }

  async function agregarItem(id) {
    const archivoId = document.getElementById('ag_archivo').value;
    if (!archivoId) { toast('Seleccione un registro.', 'pel'); return; }
    const rango = document.getElementById('ag_rango').value.trim();
    const err = MotorPDF.validarRango(rango);
    if (err) { toast(err, 'pel'); return; }
    const nuevo = {
      archivoId: archivoId, rangoPaginas: rango,
      paso: document.getElementById('ag_paso').value.trim(),
      titulo: document.getElementById('ag_titulo').value.trim(),
      sellarPaso: document.getElementById('ag_sellar').checked
    };
    await mutarPlantilla(id, function (p) {
      p.items = p.items || [];
      const maxOrden = p.items.reduce(function (m, it) { return Math.max(m, it.orden || 0); }, -1);
      p.items.push({
        id: uid(), archivoId: nuevo.archivoId, orden: maxOrden + 1,
        usarVersionActual: true, versionFijaId: null, rangoPaginas: nuevo.rangoPaginas,
        paso: nuevo.paso, titulo: nuevo.titulo, sellarPaso: nuevo.sellarPaso
      });
    });
    toast('Registro agregado.');
    renderBuilder(id);
  }

  async function moverItem(id, itemId, dir) {
    await mutarPlantilla(id, function (p) {
      p.items.sort(function (a, b) { return (a.orden || 0) - (b.orden || 0); });
      const i = p.items.findIndex(function (x) { return x.id === itemId; });
      const j = i + dir;
      if (i < 0 || j < 0 || j >= p.items.length) return;
      const tmp = p.items[i].orden; p.items[i].orden = p.items[j].orden; p.items[j].orden = tmp;
    });
    renderBuilder(id);
  }
  async function quitarItem(id, itemId) {
    if (!confirmar('¿Quitar este registro del expediente?')) return;
    await mutarPlantilla(id, function (p) { p.items = (p.items || []).filter(function (x) { return x.id !== itemId; }); });
    toast('Registro quitado.');
    renderBuilder(id);
  }

  // ---- Inserciones: PDFs intercalados entre las páginas de un ítem ----
  async function dialogoInsercion(plantillaId, itemId, insId, onDone) {
    onDone = onDone || function () { renderBuilder(plantillaId); };
    const p = await DB.get('plantillas', plantillaId);
    const item = (p.items || []).find(function (x) { return x.id === itemId; });
    if (!item) return;
    const { lista, mapa } = await archivosPorId();
    const ins = insId ? (item.inserciones || []).find(function (x) { return x.id === insId; }) : null;
    const baseA = mapa[item.archivoId];
    const basePags = paginasItem(item, mapa);
    const opc = lista.map(function (a) {
      return '<option value="' + a.id + '"' + (ins && ins.archivoId === a.id ? ' selected' : '') + '>' +
        esc((a.codigo ? a.codigo + ' — ' : '') + a.nombre) +
        ' (' + (versionActual(a) ? versionActual(a).numPaginas : 0) + ' pág.)</option>';
    }).join('');
    const cuerpo =
      '<p class="small muted">Se intercala un PDF entre las páginas de <b>' + esc(baseA ? baseA.nombre : 'este documento') +
      '</b> (' + basePags + ' pág.).</p><div class="grid">' +
      '<label class="c12">PDF a insertar<select id="in_archivo"><option value="">— Elegir —</option>' + opc + '</select></label>' +
      '<label class="c6">Insertar después de la página<input type="number" min="0" id="in_pos" value="' + (ins ? ins.despuesDePagina : '') + '" placeholder="ej. 3"></label>' +
      '<label class="c6">Páginas del PDF<input id="in_rango" value="' + (ins ? esc(ins.rangoPaginas || '') : '') + '" placeholder="todas"></label>' +
      '<label class="c12">Paso / etapa<input id="in_paso" value="' + (ins ? esc(ins.paso || '') : '') + '" placeholder="Ej. Limpieza de equipo"></label>' +
      '<label class="c12 check"><input type="checkbox" id="in_sellar"' + (ins && ins.sellarPaso ? ' checked' : '') + '> Sellar el paso en estas hojas</label>' +
      '</div><div class="small muted">0 = al inicio del documento. Para que el PDF quede como página 4, ponga <b>3</b>. ' +
      'Si lo deja vacío, se añade al final del documento.</div>';
    modal(insId ? 'Editar inserción' : 'Insertar PDF entre páginas', cuerpo, [
      { texto: 'Cancelar', clase: 'sec', onClick: function (d) { d.close(); } },
      {
        texto: 'Guardar', clase: 'prim', onClick: async function (d) {
          const archivoId = d.querySelector('#in_archivo').value;
          if (!archivoId) { toast('Seleccione un PDF.', 'pel'); return; }
          const rango = d.querySelector('#in_rango').value.trim();
          const err = MotorPDF.validarRango(rango);
          if (err) { toast(err, 'pel'); return; }
          const posV = d.querySelector('#in_pos').value.trim();
          const datos = {
            archivoId: archivoId, rangoPaginas: rango,
            despuesDePagina: posV === '' ? basePags : Math.max(0, parseInt(posV, 10) || 0),
            paso: d.querySelector('#in_paso').value.trim(),
            sellarPaso: d.querySelector('#in_sellar').checked
          };
          await mutarPlantilla(plantillaId, function (pl) {
            const it = (pl.items || []).find(function (x) { return x.id === itemId; });
            if (!it) return;
            it.inserciones = it.inserciones || [];
            if (insId) {
              const e = it.inserciones.find(function (x) { return x.id === insId; });
              if (e) {
                e.archivoId = datos.archivoId; e.rangoPaginas = datos.rangoPaginas;
                e.despuesDePagina = datos.despuesDePagina; e.paso = datos.paso; e.sellarPaso = datos.sellarPaso;
              }
            } else {
              it.inserciones.push({
                id: uid(), archivoId: datos.archivoId, usarVersionActual: true, versionFijaId: null,
                rangoPaginas: datos.rangoPaginas, despuesDePagina: datos.despuesDePagina,
                paso: datos.paso, sellarPaso: datos.sellarPaso, titulo: ''
              });
            }
          });
          d.close();
          toast(insId ? 'Inserción actualizada.' : 'PDF insertado entre páginas.');
          onDone();
        }
      }
    ]);
  }
  async function quitarInsercion(plantillaId, itemId, insId, onDone) {
    if (!confirmar('¿Quitar esta inserción?')) return;
    await mutarPlantilla(plantillaId, function (pl) {
      const it = (pl.items || []).find(function (x) { return x.id === itemId; });
      if (it) it.inserciones = (it.inserciones || []).filter(function (x) { return x.id !== insId; });
    });
    toast('Inserción quitada.');
    (onDone || function () { renderBuilder(plantillaId); })();
  }

  // Inserta un registro (con valores por defecto) en una posición concreta —
  // usado por el arrastre en la vista gráfica.
  async function insertarRegistro(plantillaId, itemId, archivoId, despuesDePagina, onDone) {
    await mutarPlantilla(plantillaId, function (pl) {
      const it = (pl.items || []).find(function (x) { return x.id === itemId; });
      if (!it) return;
      it.inserciones = it.inserciones || [];
      it.inserciones.push({
        id: uid(), archivoId: archivoId, usarVersionActual: true, versionFijaId: null,
        rangoPaginas: '', despuesDePagina: Math.max(0, despuesDePagina | 0),
        paso: '', sellarPaso: false, titulo: ''
      });
    });
    toast('Registro insertado.');
    if (onDone) onDone();
  }

  async function dialogoEditarItem(plantillaId, itemId) {
    const p = await DB.get('plantillas', plantillaId);
    const it = (p.items || []).find(function (x) { return x.id === itemId; });
    if (!it) return;
    const { mapa } = await archivosPorId();
    const a = mapa[it.archivoId];
    const opcVers = (a && a.versiones ? a.versiones : []).map(function (v) {
      return '<option value="' + v.id + '"' + (it.versionFijaId === v.id ? ' selected' : '') + '>v' + esc(v.numero) + ' (' + v.numPaginas + ' pág.)</option>';
    }).join('');
    const cuerpo =
      '<p class="fuerte">' + esc(a ? a.nombre : '(archivo eliminado)') + '</p><div class="grid">' +
      '<label class="c12">Descripción del bloque<input id="ed_titulo" value="' + esc(it.titulo || '') + '"></label>' +
      '<label class="c6">Páginas<input id="ed_rango" value="' + esc(it.rangoPaginas || '') + '" placeholder="todas"></label>' +
      '<label class="c6">Paso / etapa<input id="ed_paso" value="' + esc(it.paso || '') + '"></label>' +
      '<label class="c12 check"><input type="checkbox" id="ed_sellar"' + (it.sellarPaso ? ' checked' : '') + '> Sellar el nombre del paso en estas hojas</label>' +
      '<div class="c12"><hr></div>' +
      '<label class="c12 check"><input type="checkbox" id="ed_actual"' + (it.usarVersionActual ? ' checked' : '') + '> Usar siempre la versión actual (recomendado)</label>' +
      '<label class="c12">…o fijar una versión concreta<select id="ed_vfija"' + (it.usarVersionActual ? ' disabled' : '') + '><option value="">— Seleccionar —</option>' + opcVers + '</select></label>' +
      '</div>';
    const dlg = modal('Editar registro', cuerpo, [
      { texto: 'Cancelar', clase: 'sec', onClick: function (d) { d.close(); } },
      {
        texto: 'Guardar', clase: 'prim', onClick: async function (d) {
          const rango = d.querySelector('#ed_rango').value.trim();
          const err = MotorPDF.validarRango(rango);
          if (err) { toast(err, 'pel'); return; }
          const datos = {
            rangoPaginas: rango,
            paso: d.querySelector('#ed_paso').value.trim(),
            titulo: d.querySelector('#ed_titulo').value.trim(),
            sellarPaso: d.querySelector('#ed_sellar').checked,
            usarVersionActual: d.querySelector('#ed_actual').checked,
            versionFijaId: d.querySelector('#ed_vfija').value || null
          };
          await mutarPlantilla(plantillaId, function (pl) {
            const item = (pl.items || []).find(function (x) { return x.id === itemId; });
            if (!item) return;
            item.rangoPaginas = datos.rangoPaginas; item.paso = datos.paso; item.titulo = datos.titulo;
            item.sellarPaso = datos.sellarPaso; item.usarVersionActual = datos.usarVersionActual;
            item.versionFijaId = datos.usarVersionActual ? null : datos.versionFijaId;
          });
          d.close();
          toast('Registro actualizado.');
          renderBuilder(plantillaId);
        }
      }
    ]);
    dlg.querySelector('#ed_actual').onchange = function () { dlg.querySelector('#ed_vfija').disabled = this.checked; };
  }

  function dialogoDuplicar(plantilla) {
    const cuerpo = '<p class="small muted">Crea una copia independiente (estructura y sellos). Útil para variantes de producto.</p>' +
      '<label>Nombre de la nueva plantilla<input id="dup_nombre" value="' + esc(plantilla.nombre) + ' (copia)"></label>';
    modal('Guardar como nueva configuración', cuerpo, [
      { texto: 'Cancelar', clase: 'sec', onClick: function (d) { d.close(); } },
      {
        texto: 'Crear copia', clase: 'prim', onClick: async function (d) {
          const copia = JSON.parse(JSON.stringify(plantilla));
          copia.id = uid();
          copia.nombre = d.querySelector('#dup_nombre').value.trim() || (plantilla.nombre + ' (copia)');
          copia.items = (copia.items || []).map(function (it) {
            it.id = uid();
            it.inserciones = (it.inserciones || []).map(function (ins) { ins.id = uid(); return ins; });
            return it;
          });
          copia.creado = copia.modificado = new Date().toISOString();
          await DB.put('plantillas', copia);
          d.close();
          toast('Configuración guardada como nueva plantilla.');
          location.hash = '#/plantilla/' + copia.id;
        }
      }
    ]);
  }

  // ==================================================================
  //  VISTA GRÁFICA: insertar registros arrastrándolos sobre las páginas
  // ==================================================================
  const _docCache = {}; // versionId -> Promise<doc pdf.js>

  function pdfjsDisponible() { return !!window.pdfjsLib; }

  function docPdfjs(versionId) {
    if (!versionId) return Promise.resolve(null);
    if (_docCache[versionId]) return _docCache[versionId];
    _docCache[versionId] = DB.getBlob(versionId).then(function (ab) {
      if (!ab) return null;
      const u = new Uint8Array(ab.slice ? ab.slice(0) : ab);
      return window.pdfjsLib.getDocument({ data: u }).promise;
    });
    return _docCache[versionId];
  }

  async function pintarMiniatura(canvas, versionId, numPagina, escala) {
    try {
      const doc = await docPdfjs(versionId);
      if (!doc) return;
      const page = await doc.getPage(numPagina);
      const vp = page.getViewport({ scale: escala || 0.35 });
      canvas.width = vp.width; canvas.height = vp.height;
      await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;
      canvas.classList.add('listo');
    } catch (e) { /* miniatura no disponible */ }
  }

  function pintarLazy() {
    const canvases = Array.prototype.slice.call(document.querySelectorAll('.mini-canvas'));
    const pintar = function (c) {
      pintarMiniatura(c, c.getAttribute('data-version'),
        parseInt(c.getAttribute('data-pagina') || '1', 10),
        c.classList.contains('ins-canvas') ? 0.2 : 0.38);
    };
    if (!('IntersectionObserver' in window)) { canvases.forEach(pintar); return; }
    const obs = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (en) {
        if (en.isIntersecting) { obs.unobserve(en.target); pintar(en.target); }
      });
    }, { root: document.getElementById('paginasGrafico'), rootMargin: '400px' });
    canvases.forEach(function (c) { obs.observe(c); });
  }

  async function renderGrafico(plantillaId, itemId) {
    const plantilla = await DB.get('plantillas', plantillaId);
    if (!plantilla) { app.innerHTML = '<div class="card">Plantilla no encontrada.</div>'; return; }
    const item = (plantilla.items || []).find(function (x) { return x.id === itemId; });
    const volver = '#/plantilla/' + plantillaId;
    if (!item) { location.hash = volver; return; }
    const { lista, mapa } = await archivosPorId();
    const archivoBase = mapa[item.archivoId];
    const vBase = versionEfectivaMeta(archivoBase, item);

    if (!pdfjsDisponible() || !vBase) {
      app.innerHTML = '<div class="card"><p>' +
        (vBase ? 'No se pudo cargar el visor de páginas.' : 'Este bloque no tiene un PDF con versión disponible.') +
        '</p><a class="btn" href="' + volver + '">‹ Volver</a></div>';
      return;
    }

    const baseIndices = MotorPDF.parseRango(item.rangoPaginas, vBase.numPaginas || 0);
    const inserciones = (item.inserciones || []).slice().sort(function (a, b) { return (a.despuesDePagina || 0) - (b.despuesDePagina || 0); });

    const paleta = lista.map(function (a) {
      const va = versionActual(a);
      return '<div class="reg-card" draggable="true" data-archivo="' + a.id + '">' +
        '<div class="reg-nom">' + esc(a.nombre) + '</div>' +
        '<div class="muted small">' + esc(TIPOS[a.tipo] || a.tipo) + ' · ' + (va ? va.numPaginas : 0) + ' pág.</div></div>';
    }).join('') || '<p class="muted small">No hay registros. <a class="enlace" href="#/archivos">Cargue PDFs</a>.</p>';

    function slotHTML(pos) {
      const ins = inserciones.filter(function (x) {
        const dp = x.despuesDePagina || 0;
        if (pos === 0) return dp <= 0;
        if (pos === baseIndices.length) return dp >= pos;
        return dp === pos;
      });
      const cards = ins.map(function (x) {
        const ia = mapa[x.archivoId];
        const v = versionEfectivaMeta(ia, x);
        return '<div class="ins-mini">' +
          '<canvas class="mini-canvas ins-canvas" data-version="' + (v ? v.id : '') + '"></canvas>' +
          '<div class="ins-mini-nom">' + esc(ia ? ia.nombre : '(eliminado)') + (x.paso ? '<br><span class="muted">' + esc(x.paso) + '</span>' : '') + '</div>' +
          '<div class="ins-mini-btns"><button class="btn mini prim" data-edit-ins="' + x.id + '" title="Editar">✎</button>' +
          '<button class="btn mini pel" data-quita-ins="' + x.id + '" title="Quitar">✕</button></div></div>';
      }).join('');
      const etiqueta = pos === 0 ? 'Al inicio' : (pos === baseIndices.length ? 'Al final' : '↳ tras pág. ' + pos);
      return '<div class="slot" data-pos="' + pos + '"><div class="slot-cap">' + etiqueta + '</div>' + cards +
        '<div class="slot-drop">+ soltar</div></div>';
    }

    let tira = slotHTML(0);
    for (let i = 0; i < baseIndices.length; i++) {
      tira += '<div class="pagina-card" data-pos="' + (i + 1) + '">' +
        '<canvas class="mini-canvas base-canvas" data-version="' + vBase.id + '" data-pagina="' + (baseIndices[i] + 1) + '"></canvas>' +
        '<div class="pagina-cap">Pág. ' + (i + 1) + '</div></div>';
      tira += slotHTML(i + 1);
    }

    app.innerHTML =
      '<div class="barra"><div><a href="' + volver + '" class="enlace small">‹ Volver al armador</a>' +
      '<h2>Inserción gráfica — ' + esc(archivoBase.nombre) + '</h2>' +
      '<div class="chips"><span class="chip">' + baseIndices.length + ' páginas</span>' +
      '<span class="chip prim">' + inserciones.length + ' inserción(es)</span></div></div></div>' +
      '<div class="aviso">Arrastre un registro de la izquierda y suéltelo <b>entre las páginas</b> de la fórmula maestra (sobre la página o en el hueco donde debe ir).</div>' +
      '<div class="grafico"><aside class="paleta"><div class="paleta-tit">Registros / formularios</div>' +
      paleta + '<a class="btn" href="#/archivos" style="margin-top:10px">+ Cargar PDF</a></aside>' +
      '<div class="paginas-grafico" id="paginasGrafico">' + tira + '</div></div>';

    pintarLazy();

    let arrastrando = null;
    app.querySelectorAll('.reg-card').forEach(function (card) {
      card.addEventListener('dragstart', function (e) {
        arrastrando = card.getAttribute('data-archivo');
        try { e.dataTransfer.setData('text/plain', arrastrando); e.dataTransfer.effectAllowed = 'copy'; } catch (x) { }
      });
      card.addEventListener('dragend', function () { arrastrando = null; });
    });
    function posDe(el) {
      const s = el.closest('.slot'); if (s) return parseInt(s.getAttribute('data-pos'), 10);
      const pg = el.closest('.pagina-card'); if (pg) return parseInt(pg.getAttribute('data-pos'), 10);
      return null;
    }
    const cont = document.getElementById('paginasGrafico');
    cont.querySelectorAll('.slot, .pagina-card').forEach(function (z) {
      z.addEventListener('dragover', function (e) { e.preventDefault(); z.classList.add('zona-activa'); });
      z.addEventListener('dragleave', function () { z.classList.remove('zona-activa'); });
      z.addEventListener('drop', function (e) {
        e.preventDefault(); z.classList.remove('zona-activa');
        let archivoId = arrastrando;
        try { archivoId = e.dataTransfer.getData('text/plain') || arrastrando; } catch (x) { }
        const pos = posDe(z);
        if (archivoId && pos != null) {
          insertarRegistro(plantillaId, itemId, archivoId, pos, function () { renderGrafico(plantillaId, itemId); });
        }
      });
    });
    app.querySelectorAll('[data-edit-ins]').forEach(function (b) {
      b.onclick = function () { dialogoInsercion(plantillaId, itemId, b.getAttribute('data-edit-ins'), function () { renderGrafico(plantillaId, itemId); }); };
    });
    app.querySelectorAll('[data-quita-ins]').forEach(function (b) {
      b.onclick = function () { quitarInsercion(plantillaId, itemId, b.getAttribute('data-quita-ins'), function () { renderGrafico(plantillaId, itemId); }); };
    });
  }

  // ==================================================================
  //  Vista previa y generación
  // ==================================================================
  async function previsualizar(plantillaId) {
    const p = await DB.get('plantillas', plantillaId);
    const { mapa } = await archivosPorId();
    let bytes;
    try {
      bytes = await MotorPDF.ensamblar(p, obtenerBytesFactory(mapa),
        { producto: p.producto || '', lote: '(LOTE)', codigo: p.codigo || '', fecha: fmtFecha(hoyISO()), version: p.version || '' });
    } catch (e) { toast('Error al generar la vista previa: ' + e.message, 'pel'); return; }
    if (!bytes) bytes = await MotorPDF.pdfMensaje('La plantilla no tiene registros con páginas.');
    verPdf('Vista previa — ' + p.nombre, bytes);
  }

  function verPdf(titulo, bytes) {
    const blob = new Blob([bytes], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    modal(titulo,
      '<iframe class="visor" src="' + url + '"></iframe>' +
      '<div class="small muted">Si no se ve, <a class="enlace" href="' + url + '" target="_blank" rel="noopener">ábralo en una pestaña</a>.</div>',
      [{ texto: 'Cerrar', clase: 'sec', onClick: function (d) { d.close(); } }],
      { ancho: true, alCerrar: function () { URL.revokeObjectURL(url); } });
  }

  async function dialogoGenerar(plantillaId) {
    const p = await DB.get('plantillas', plantillaId);
    const cuerpo = '<div class="grid">' +
      '<label class="c6">Número de lote<input id="g_lote" placeholder="Ej. L-2026-0345"></label>' +
      '<label class="c6">Fecha<input type="date" id="g_fecha" value="' + hoyISO() + '"></label>' +
      '<label class="c7">Producto<input id="g_producto" value="' + esc(p.producto || '') + '"></label>' +
      '<label class="c5">Código<input id="g_codigo" value="' + esc(p.codigo || '') + '"></label>' +
      '<label class="c12">Nombre del expediente (al guardar)<input id="g_nombre" placeholder="' + esc(p.nombre) + ' — Lote …"></label>' +
      '<div class="c12"><b>¿Qué desea hacer?</b></div>' +
      '<label class="c12 check"><input type="radio" name="g_accion" value="ambos" checked> Guardar y descargar el PDF</label>' +
      '<label class="c12 check"><input type="radio" name="g_accion" value="guardar"> Solo guardar (queda en «Expedientes armados»)</label>' +
      '<label class="c12 check"><input type="radio" name="g_accion" value="descargar"> Solo descargar (no guardar)</label>' +
      '</div>';
    modal('Generar expediente — ' + p.nombre, cuerpo, [
      { texto: 'Vista previa', clase: 'sec', onClick: function () { previsualizar(plantillaId); } },
      { texto: 'Cancelar', clase: 'sec', onClick: function (d) { d.close(); } },
      {
        texto: 'Generar', clase: 'ok', onClick: async function (d) {
          const lote = d.querySelector('#g_lote').value.trim();
          const producto = d.querySelector('#g_producto').value.trim() || p.producto || '';
          const codigo = d.querySelector('#g_codigo').value.trim() || p.codigo || '';
          const fecha = d.querySelector('#g_fecha').value || hoyISO();
          const accion = d.querySelector('input[name="g_accion"]:checked').value;
          const { mapa } = await archivosPorId();
          let bytes;
          try {
            bytes = await MotorPDF.ensamblar(p, obtenerBytesFactory(mapa),
              { producto: producto, lote: lote, codigo: codigo, fecha: fmtFecha(fecha), version: p.version || '' });
          } catch (e) { toast('Error al generar: ' + e.message, 'pel'); return; }
          if (!bytes) { toast('La plantilla no tiene registros con páginas.', 'pel'); return; }
          const nombreArch = slug(codigo || p.nombre) + (lote ? '_lote_' + slug(lote) : '') + '.pdf';
          if (accion === 'descargar' || accion === 'ambos') descargar(nombreArch, bytes, 'application/pdf');
          if (accion === 'guardar' || accion === 'ambos') {
            const expId = uid();
            await DB.putBlob(expId, bytes.buffer ? bytes.buffer.slice(0) : bytes);
            const exp = {
              id: expId, plantillaId: p.id,
              nombre: d.querySelector('#g_nombre').value.trim() || (p.nombre + (lote ? ' — Lote ' + lote : '')),
              producto: producto, codigo: codigo, lote: lote, fecha: fecha,
              numPaginas: await MotorPDF.contarPaginas(bytes), tamano: bytes.length,
              fechaGeneracion: new Date().toISOString()
            };
            await DB.put('expedientes', exp);
            toast('Expediente generado y guardado.');
          } else {
            toast('Expediente generado.');
          }
          d.close();
        }
      }
    ]);
  }

  // ==================================================================
  //  VISTA: ARCHIVOS (registros / PDFs)
  // ==================================================================
  async function renderArchivos() {
    const arr = await DB.getAll('archivos');
    arr.sort(function (a, b) { return (a.tipo + a.nombre).localeCompare(b.tipo + b.nombre); });
    let filas = arr.map(function (a) {
      const v = versionActual(a);
      return '<tr>' +
        '<td><a class="enlace fuerte" href="#/archivo/' + a.id + '">' + esc(a.nombre) + '</a></td>' +
        '<td>' + esc(a.codigo || '—') + '</td>' +
        '<td><span class="chip">' + esc(TIPOS[a.tipo] || a.tipo) + '</span></td>' +
        '<td>v' + (v ? esc(v.numero) : '—') + '</td>' +
        '<td class="centro">' + (v ? v.numPaginas : 0) + '</td>' +
        '<td class="der">' +
          '<button class="btn mini" data-ver="' + a.id + '" title="Ver PDF actual">👁</button> ' +
          '<a class="btn mini prim" href="#/archivo/' + a.id + '" title="Versiones">≡</a></td></tr>';
    }).join('');
    if (!arr.length) filas = '<tr><td colspan="6" class="centro muted pad">No hay archivos. Cargue el primero.</td></tr>';

    app.innerHTML =
      '<div class="aviso">PDF reutilizables (fórmulas maestras, registros, anexos…) con <b>historial de versiones</b>. ' +
      'Cuando un registro cambie, suba su nueva versión: los expedientes se actualizan al regenerarse.</div>' +
      '<div class="barra"><h2>Registros / PDFs</h2><button class="btn prim" id="btnCargar">⬆ Cargar PDF</button></div>' +
      '<div class="card sinpad"><table class="tabla"><thead><tr><th>Nombre</th><th>Código</th><th>Tipo</th>' +
      '<th>Ver. actual</th><th class="centro">Págs.</th><th></th></tr></thead><tbody>' + filas + '</tbody></table></div>';

    document.getElementById('btnCargar').onclick = dialogoCargarArchivo;
    app.querySelectorAll('[data-ver]').forEach(function (b) {
      b.onclick = function () { verArchivoActual(b.getAttribute('data-ver')); };
    });
  }

  async function verArchivoActual(id) {
    const a = await DB.get('archivos', id);
    const v = versionActual(a);
    if (!v) { toast('Sin versión.', 'pel'); return; }
    const bytes = await DB.getBlob(v.id);
    verPdf(a.nombre + ' (v' + v.numero + ')', bytes);
  }

  function dialogoCargarArchivo() {
    const opcTipos = Object.keys(TIPOS).map(function (k) {
      return '<option value="' + k + '"' + (k === 'REGISTRO' ? ' selected' : '') + '>' + TIPOS[k] + '</option>';
    }).join('');
    const cuerpo = '<div class="grid">' +
      '<label class="c12">Archivo PDF *<input type="file" id="ca_file" accept="application/pdf,.pdf"></label>' +
      '<label class="c8">Nombre<input id="ca_nombre" placeholder="Si lo deja vacío se usa el del archivo"></label>' +
      '<label class="c4">Versión<input id="ca_version" value="01"></label>' +
      '<label class="c6">Código<input id="ca_codigo" placeholder="Ej. FOR-PRD-014"></label>' +
      '<label class="c6">Tipo<select id="ca_tipo">' + opcTipos + '</select></label>' +
      '<label class="c12">Descripción<textarea id="ca_desc" rows="2"></textarea></label>' +
      '</div>';
    modal('Cargar registro / PDF', cuerpo, [
      { texto: 'Cancelar', clase: 'sec', onClick: function (d) { d.close(); } },
      {
        texto: 'Cargar', clase: 'prim', onClick: async function (d) {
          const file = d.querySelector('#ca_file').files[0];
          if (!file) { toast('Seleccione un PDF.', 'pel'); return; }
          const bytes = await leerBytes(file);
          if (!(await MotorPDF.esPdfValido(bytes))) { toast('El archivo no es un PDF válido.', 'pel'); return; }
          const versionId = uid();
          const numPag = await MotorPDF.contarPaginas(bytes);
          const archivo = {
            id: uid(),
            nombre: d.querySelector('#ca_nombre').value.trim() || file.name,
            codigo: d.querySelector('#ca_codigo').value.trim(),
            tipo: d.querySelector('#ca_tipo').value,
            descripcion: d.querySelector('#ca_desc').value.trim(),
            versionActualId: versionId,
            versiones: [{
              id: versionId, numero: d.querySelector('#ca_version').value.trim() || '01',
              fecha: new Date().toISOString(), nombreOriginal: file.name,
              numPaginas: numPag, tamano: bytes.byteLength, descripcionCambio: 'Versión inicial.'
            }],
            creado: new Date().toISOString()
          };
          await DB.putBlob(versionId, bytes);
          await DB.put('archivos', archivo);
          d.close();
          toast('Archivo cargado (' + numPag + ' pág.).');
          if (location.hash === '#/archivo/' + archivo.id) router();
          else location.hash = '#/archivo/' + archivo.id;
        }
      }
    ]);
  }

  // ==================================================================
  //  VISTA: DETALLE ARCHIVO (versiones)
  // ==================================================================
  async function renderArchivoDetalle(id) {
    const a = await DB.get('archivos', id);
    if (!a) { app.innerHTML = '<div class="card">Archivo no encontrado.</div>'; return; }
    const versiones = (a.versiones || []).slice().reverse();
    const filas = versiones.map(function (v) {
      const esActual = v.id === a.versionActualId;
      return '<tr' + (esActual ? ' class="fila-activa"' : '') + '>' +
        '<td class="fuerte">v' + esc(v.numero) + (esActual ? ' ✔' : '') + '</td>' +
        '<td>' + v.numPaginas + '</td><td class="small">' + tamanoLegible(v.tamano) + '</td>' +
        '<td class="small">' + fmtFechaHora(v.fecha) + '</td>' +
        '<td class="small">' + esc(v.descripcionCambio || '—') + '</td>' +
        '<td class="der"><button class="btn mini" data-verv="' + v.id + '" title="Ver">👁</button> ' +
          (esActual ? '' : '<button class="btn mini prim" data-actual="' + v.id + '" title="Marcar como actual">★</button>') +
        '</td></tr>';
    }).join('');

    app.innerHTML =
      '<div class="barra"><div><a href="#/archivos" class="enlace small">‹ Registros / PDFs</a><h2>' + esc(a.nombre) + '</h2>' +
      '<div class="chips"><span class="chip">' + esc(TIPOS[a.tipo] || a.tipo) + '</span>' +
        (a.codigo ? '<span class="chip">' + esc(a.codigo) + '</span>' : '') +
        '<span class="chip prim">actual: v' + (versionActual(a) ? esc(versionActual(a).numero) : '—') + '</span></div></div>' +
      '<button class="btn pel" id="btnDelArch">🗑 Eliminar archivo</button></div>' +
      (a.descripcion ? '<div class="card small">' + esc(a.descripcion) + '</div>' : '') +
      '<div class="cols"><div class="col-izq"><div class="card sinpad"><div class="card-head">Historial de versiones</div>' +
        '<table class="tabla"><thead><tr><th>Versión</th><th>Págs.</th><th>Tamaño</th><th>Fecha</th><th>Cambios</th><th></th></tr></thead>' +
        '<tbody>' + filas + '</tbody></table></div></div>' +
      '<div class="col-der"><div class="card"><div class="card-head">Subir nueva versión</div><div class="grid">' +
        '<label class="c12">Archivo PDF *<input type="file" id="nv_file" accept="application/pdf,.pdf"></label>' +
        '<label class="c12">Número de versión<input id="nv_num" placeholder="Auto (siguiente) si lo deja vacío"></label>' +
        '<label class="c12">Cambios realizados<textarea id="nv_desc" rows="2"></textarea></label>' +
        '<div class="c12"><button class="btn prim" id="btnNuevaVer">⬆ Cargar y marcar como actual</button></div>' +
        '</div></div></div></div>';

    document.getElementById('btnNuevaVer').onclick = function () { subirNuevaVersion(id); };
    document.getElementById('btnDelArch').onclick = function () { eliminarArchivo(id); };
    app.querySelectorAll('[data-verv]').forEach(function (b) {
      b.onclick = async function () {
        const bytes = await DB.getBlob(b.getAttribute('data-verv'));
        verPdf(a.nombre, bytes);
      };
    });
    app.querySelectorAll('[data-actual]').forEach(function (b) {
      b.onclick = async function () {
        a.versionActualId = b.getAttribute('data-actual');
        await DB.put('archivos', a);
        toast('Versión actual actualizada.');
        renderArchivoDetalle(id);
      };
    });
  }

  function siguienteVersion(num) {
    const n = parseInt(num, 10);
    return isNaN(n) ? '01' : ('0' + (n + 1)).slice(-2);
  }

  async function subirNuevaVersion(id) {
    const a = await DB.get('archivos', id);
    const file = document.getElementById('nv_file').files[0];
    if (!file) { toast('Seleccione un PDF.', 'pel'); return; }
    const bytes = await leerBytes(file);
    if (!(await MotorPDF.esPdfValido(bytes))) { toast('El archivo no es un PDF válido.', 'pel'); return; }
    const ultima = a.versiones[a.versiones.length - 1];
    const num = document.getElementById('nv_num').value.trim() || siguienteVersion(ultima ? ultima.numero : '00');
    const versionId = uid();
    const numPag = await MotorPDF.contarPaginas(bytes);
    a.versiones.push({
      id: versionId, numero: num, fecha: new Date().toISOString(), nombreOriginal: file.name,
      numPaginas: numPag, tamano: bytes.byteLength,
      descripcionCambio: document.getElementById('nv_desc').value.trim()
    });
    a.versionActualId = versionId;
    await DB.putBlob(versionId, bytes);
    await DB.put('archivos', a);
    toast('Versión ' + num + ' cargada y marcada como actual.');
    renderArchivoDetalle(id);
  }

  async function eliminarArchivo(id) {
    const plantillas = await DB.getAll('plantillas');
    let enUso = 0;
    plantillas.forEach(function (p) { (p.items || []).forEach(function (it) { if (it.archivoId === id) enUso++; }); });
    if (enUso) { toast('No se puede eliminar: el archivo se usa en ' + enUso + ' registro(s) de plantillas.', 'pel'); return; }
    if (!confirmar('¿Eliminar este archivo y todas sus versiones?')) return;
    const a = await DB.get('archivos', id);
    for (const v of (a.versiones || [])) await DB.delBlob(v.id);
    await DB.del('archivos', id);
    toast('Archivo eliminado.');
    location.hash = '#/archivos';
  }

  // ==================================================================
  //  VISTA: EXPEDIENTES ARMADOS
  // ==================================================================
  async function renderArmados() {
    const arr = await DB.getAll('expedientes');
    arr.sort(function (a, b) { return (b.fechaGeneracion || '').localeCompare(a.fechaGeneracion || ''); });
    let filas = arr.map(function (e) {
      return '<tr>' +
        '<td class="fuerte">' + esc(e.nombre) + (e.codigo ? '<br><span class="muted small">' + esc(e.codigo) + '</span>' : '') + '</td>' +
        '<td>' + esc(e.producto || '—') + '</td><td>' + esc(e.lote || '—') + '</td>' +
        '<td class="centro">' + (e.numPaginas || 0) + '</td><td class="small">' + fmtFechaHora(e.fechaGeneracion) + '</td>' +
        '<td class="der">' +
          '<button class="btn mini" data-ver="' + e.id + '" title="Ver">👁</button> ' +
          '<button class="btn mini pel" data-desc="' + e.id + '" title="Descargar">⬇</button> ' +
          (e.plantillaId ? '<button class="btn mini prim" data-regen="' + e.id + '" title="Regenerar con versiones vigentes">↻</button> ' : '') +
          '<button class="btn mini" data-del="' + e.id + '" title="Eliminar">🗑</button></td></tr>';
    }).join('');
    if (!arr.length) filas = '<tr><td colspan="6" class="centro muted pad">No hay expedientes armados todavía.</td></tr>';

    app.innerHTML =
      '<div class="barra"><h2>Expedientes armados</h2></div>' +
      '<div class="card sinpad"><table class="tabla"><thead><tr><th>Expediente</th><th>Producto</th><th>Lote</th>' +
      '<th class="centro">Págs.</th><th>Generado</th><th></th></tr></thead><tbody>' + filas + '</tbody></table></div>';

    app.querySelectorAll('[data-ver]').forEach(function (b) {
      b.onclick = async function () { const e = await DB.get('expedientes', b.getAttribute('data-ver')); verPdf(e.nombre, await DB.getBlob(e.id)); };
    });
    app.querySelectorAll('[data-desc]').forEach(function (b) {
      b.onclick = async function () {
        const e = await DB.get('expedientes', b.getAttribute('data-desc'));
        descargar(slug(e.codigo || e.nombre) + (e.lote ? '_lote_' + slug(e.lote) : '') + '.pdf', await DB.getBlob(e.id), 'application/pdf');
      };
    });
    app.querySelectorAll('[data-regen]').forEach(function (b) { b.onclick = function () { regenerar(b.getAttribute('data-regen')); }; });
    app.querySelectorAll('[data-del]').forEach(function (b) {
      b.onclick = async function () {
        if (!confirmar('¿Eliminar este expediente armado?')) return;
        const id = b.getAttribute('data-del');
        await DB.delBlob(id); await DB.del('expedientes', id);
        toast('Expediente eliminado.'); renderArmados();
      };
    });
  }

  async function regenerar(id) {
    const e = await DB.get('expedientes', id);
    const p = await DB.get('plantillas', e.plantillaId);
    if (!p) { toast('La plantilla original ya no existe.', 'pel'); return; }
    if (!confirmar('¿Regenerar con las versiones vigentes de cada registro?')) return;
    const { mapa } = await archivosPorId();
    const bytes = await MotorPDF.ensamblar(p, obtenerBytesFactory(mapa),
      { producto: e.producto || '', lote: e.lote || '', codigo: e.codigo || '', fecha: fmtFecha(e.fecha || hoyISO()), version: p.version || '' });
    if (!bytes) { toast('La plantilla no tiene páginas.', 'pel'); return; }
    await DB.putBlob(id, bytes.buffer ? bytes.buffer.slice(0) : bytes);
    e.numPaginas = await MotorPDF.contarPaginas(bytes);
    e.tamano = bytes.length;
    e.fechaGeneracion = new Date().toISOString();
    await DB.put('expedientes', e);
    toast('Expediente regenerado con las versiones vigentes (' + e.numPaginas + ' págs.).');
    renderArmados();
  }

  // ==================================================================
  //  VISTA: DATOS (respaldo / restaurar)
  // ==================================================================
  function abToBase64(ab) {
    let bin = '';
    const bytes = new Uint8Array(ab);
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    return btoa(bin);
  }
  function base64ToAb(b64) {
    const bin = atob(b64);
    const len = bin.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
    return bytes.buffer;
  }

  async function renderDatos() {
    let uso = '';
    if (navigator.storage && navigator.storage.estimate) {
      try { const est = await navigator.storage.estimate(); uso = 'Uso aproximado: ' + tamanoLegible(est.usage || 0) + ' de ' + tamanoLegible(est.quota || 0) + '.'; } catch (e) { }
    }
    const nA = (await DB.getAll('archivos')).length;
    const nP = (await DB.getAll('plantillas')).length;
    const nE = (await DB.getAll('expedientes')).length;
    app.innerHTML =
      '<div class="barra"><h2>Datos y respaldo</h2></div>' +
      '<div class="aviso">Toda la información vive en este navegador y equipo (no se envía a internet). ' +
      'Use <b>Exportar respaldo</b> para guardar una copia o para llevar sus datos a otra PC.</div>' +
      '<div class="card"><p>Contenido actual: <b>' + nA + '</b> archivos, <b>' + nP + '</b> plantillas, <b>' + nE + '</b> expedientes armados.</p>' +
      '<p class="small muted">' + esc(uso) + '</p>' +
      '<div class="acciones"><button class="btn prim" id="btnExport">⬇ Exportar respaldo (.json)</button>' +
      '<label class="btn sec" style="cursor:pointer">⬆ Importar respaldo<input type="file" id="impFile" accept="application/json,.json" hidden></label>' +
      '<button class="btn pel" id="btnBorrar">Borrar todos los datos</button></div></div>';

    document.getElementById('btnExport').onclick = exportarDatos;
    document.getElementById('btnBorrar').onclick = borrarTodo;
    document.getElementById('impFile').onchange = function (e) { if (e.target.files[0]) importarDatos(e.target.files[0]); };
  }

  async function exportarDatos() {
    const archivos = await DB.getAll('archivos');
    const plantillas = await DB.getAll('plantillas');
    const expedientes = await DB.getAll('expedientes');
    const blobs = await DB.getAll('blobs');
    const data = {
      app: 'armador-expedientes', version: 1, fecha: new Date().toISOString(),
      archivos: archivos, plantillas: plantillas, expedientes: expedientes,
      blobs: blobs.map(function (b) { return { id: b.id, datos: abToBase64(b.datos) }; })
    };
    descargar('respaldo-expedientes-' + hoyISO() + '.json', JSON.stringify(data), 'application/json');
    toast('Respaldo exportado.');
  }

  async function importarDatos(file) {
    if (!confirmar('Importar reemplazará TODOS los datos actuales por los del respaldo. ¿Continuar?')) return;
    let data;
    try { data = JSON.parse(await file.text()); } catch (e) { toast('Archivo inválido.', 'pel'); return; }
    if (data.app !== 'armador-expedientes') { toast('No es un respaldo válido de esta aplicación.', 'pel'); return; }
    for (const s of DB.STORES) await DB.clear(s);
    for (const a of (data.archivos || [])) await DB.put('archivos', a);
    for (const p of (data.plantillas || [])) await DB.put('plantillas', p);
    for (const e of (data.expedientes || [])) await DB.put('expedientes', e);
    for (const b of (data.blobs || [])) await DB.putBlob(b.id, base64ToAb(b.datos));
    toast('Respaldo importado.');
    location.hash = '#/plantillas';
    router();
  }

  async function borrarTodo() {
    if (!confirmar('¿Borrar TODOS los datos (archivos, plantillas y expedientes)? No se puede deshacer.')) return;
    if (!confirmar('Confirme de nuevo: esto eliminará todo de forma permanente.')) return;
    for (const s of DB.STORES) await DB.clear(s);
    toast('Todos los datos fueron borrados.');
    location.hash = '#/plantillas';
    router();
  }

  // ==================================================================
  //  Router
  // ==================================================================
  function actualizarNav(vista) {
    document.querySelectorAll('nav a[data-route]').forEach(function (a) {
      a.classList.toggle('activo', a.getAttribute('data-route') === vista);
    });
  }

  async function router() {
    const hash = location.hash || '#/plantillas';
    const partes = hash.replace(/^#\/?/, '').split('/');
    const vista = partes[0] || 'plantillas';
    try {
      if (vista === 'archivos') await renderArchivos();
      else if (vista === 'archivo') await renderArchivoDetalle(partes[1]);
      else if (vista === 'plantilla') await renderBuilder(partes[1]);
      else if (vista === 'grafico') await renderGrafico(partes[1], partes[2]);
      else if (vista === 'armados') await renderArmados();
      else if (vista === 'datos') await renderDatos();
      else await renderPlantillas();
    } catch (e) { mostrarError(e); }
    actualizarNav((vista === 'plantilla' || vista === 'grafico') ? 'plantillas' : (vista === 'archivo' ? 'archivos' : vista));
    window.scrollTo(0, 0);
  }

  window.addEventListener('hashchange', router);
  window.addEventListener('DOMContentLoaded', function () {
    DB.abrir().then(router).catch(mostrarError);
  });
})();
