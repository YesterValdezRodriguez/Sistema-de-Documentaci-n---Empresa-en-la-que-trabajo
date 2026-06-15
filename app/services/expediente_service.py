"""Motor de armado de expedientes.

Une las páginas de varios PDF (pypdf) en el orden definido por una plantilla y
aplica una capa de sellos/foliado generada con ReportLab. Trabaja 100 % en
memoria (BytesIO): no crea archivos temporales ni necesita permisos especiales.
"""
from io import BytesIO
from datetime import date

from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.pdfgen import canvas
from reportlab.lib import colors

MARGEN = 20  # puntos desde el borde (~0.28")

AZUL = colors.HexColor('#1B3A6B')
ROJO = colors.HexColor('#C0392B')


# --------------------------------------------------------------- utilidades

def contar_paginas(datos):
    """Número de páginas de un PDF en bytes (0 si no se puede leer)."""
    try:
        return len(PdfReader(BytesIO(datos)).pages)
    except Exception:
        return 0


def es_pdf_valido(datos):
    """True si los bytes corresponden a un PDF legible con al menos una página."""
    try:
        return len(PdfReader(BytesIO(datos)).pages) > 0
    except Exception:
        return False


def parse_rango_paginas(rango, total):
    """Convierte '1-3,5,8-' en una lista de índices base-0 válidos.

    Cadena vacía = todas las páginas. Tolera espacios, rangos abiertos
    ('8-' = de la 8 al final) y descarta números fuera de rango.
    """
    if total <= 0:
        return []
    if not rango or not rango.strip():
        return list(range(total))
    indices = []
    for parte in rango.split(','):
        parte = parte.strip()
        if not parte:
            continue
        if '-' in parte:
            a, _, b = parte.partition('-')
            try:
                ini = int(a) if a.strip() else 1
                fin = int(b) if b.strip() else total
            except ValueError:
                continue
            if ini > fin:
                ini, fin = fin, ini
            for n in range(ini, fin + 1):
                if 1 <= n <= total:
                    indices.append(n - 1)
        else:
            try:
                n = int(parte)
            except ValueError:
                continue
            if 1 <= n <= total:
                indices.append(n - 1)
    return indices


def validar_rango(rango):
    """Devuelve None si el rango es sintácticamente válido, o un mensaje."""
    if not rango or not rango.strip():
        return None
    for parte in rango.split(','):
        parte = parte.strip()
        if not parte:
            continue
        cuerpo = parte.replace('-', '', 1) if '-' in parte else parte
        cuerpo = cuerpo.replace('-', '')
        if cuerpo and not cuerpo.isdigit():
            return f'Rango de páginas inválido: «{parte}»'
    return None


# ------------------------------------------------------------------- sellos

def _coords(posicion, w, h, tam):
    """Coordenada (x, y) y alineación para una posición de sello."""
    izq = MARGEN
    cen = w / 2.0
    der = w - MARGEN
    inf = MARGEN
    sup = h - MARGEN - tam
    mapa = {
        'SUP_IZQ': (izq, sup, 'left'),
        'SUP_CEN': (cen, sup, 'center'),
        'SUP_DER': (der, sup, 'right'),
        'INF_IZQ': (izq, inf, 'left'),
        'INF_CEN': (cen, inf, 'center'),
        'INF_DER': (der, inf, 'right'),
    }
    return mapa.get(posicion, mapa['INF_DER'])


def _formatear(plantilla_texto, contexto):
    """Reemplaza {marcadores} de forma tolerante (deja el texto si algo falla)."""
    if not plantilla_texto:
        return ''
    try:
        return plantilla_texto.format(**contexto)
    except (KeyError, IndexError, ValueError):
        return plantilla_texto


def pdf_mensaje(texto):
    """Genera un PDF de una página con un mensaje centrado (para vistas vacías)."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.setFont('Helvetica-Bold', 13)
    c.setFillColor(AZUL)
    c.drawCentredString(306, 430, texto[:90])
    if len(texto) > 90:
        c.setFont('Helvetica', 11)
        c.drawCentredString(306, 410, texto[90:180])
    c.save()
    buf.seek(0)
    return buf


def _crear_overlay(w, h, lineas):
    """Crea una página-capa del tamaño dado con los textos de sello.

    `lineas` = lista de tuplas (texto, posicion, tam, color). Devuelve la página
    pypdf de la capa, o None si no hay nada que dibujar.
    """
    lineas = [ln for ln in lineas if ln[0]]
    if not lineas:
        return None
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    for texto, posicion, tam, color in lineas:
        x, y, align = _coords(posicion, w, h, tam)
        c.setFont('Helvetica-Bold', tam)
        c.setFillColor(color)
        if align == 'left':
            c.drawString(x, y, texto)
        elif align == 'right':
            c.drawRightString(x, y, texto)
        else:
            c.drawCentredString(x, y, texto)
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def _lineas_de_sello(plantilla, item, contexto_pagina):
    """Construye las líneas de sello para una página, sin solaparlas."""
    lineas = []
    # Encabezado (parte superior)
    if plantilla.mostrar_encabezado and plantilla.formato_encabezado:
        lineas.append((_formatear(plantilla.formato_encabezado, contexto_pagina),
                       plantilla.posicion_encabezado, 8, AZUL))
    # Sello tipo "ORIGINAL / COPIA CONTROLADA"
    if plantilla.texto_sello:
        lineas.append((_formatear(plantilla.texto_sello, contexto_pagina),
                       plantilla.posicion_sello, 10, ROJO))
    # Etiqueta de paso del ítem (p. ej. "PASO: Pesada")
    if item is not None and item.sellar_paso and item.paso:
        lineas.append((f'PASO: {item.paso}', 'SUP_IZQ', 9, AZUL))
    # Foliado (parte inferior)
    if plantilla.foliar and plantilla.formato_folio:
        lineas.append((_formatear(plantilla.formato_folio, contexto_pagina),
                       plantilla.posicion_folio, 8, colors.black))
    return lineas


# --------------------------------------------------------------- ensamblado

def _contexto_base(plantilla, contexto):
    contexto = contexto or {}
    return {
        'producto': contexto.get('producto') or plantilla.producto or '',
        'lote': contexto.get('lote', '') or '',
        'codigo': contexto.get('codigo') or plantilla.codigo or '',
        'fecha': contexto.get('fecha') or date.today().strftime('%d/%m/%Y'),
        'plantilla': plantilla.nombre or '',
        'version': contexto.get('version') or plantilla.version or '',
    }


def ensamblar(plantilla, contexto=None):
    """Arma el PDF del expediente y devuelve (BytesIO, num_paginas).

    Recolecta las páginas de cada ítem (usando su versión efectiva y su rango),
    las une en orden y aplica los sellos de la plantilla. Las páginas sin
    versión disponible se omiten.
    """
    ctx = _contexto_base(plantilla, contexto)

    # 1) Recolectar (página, ítem de origen) en orden
    paginas_meta = []
    for item in sorted(plantilla.items, key=lambda it: it.orden):
        version = item.version_efectiva()
        if not version or not version.datos:
            continue
        try:
            reader = PdfReader(BytesIO(version.datos))
        except Exception:
            continue
        total_v = len(reader.pages)
        for i in parse_rango_paginas(item.rango_paginas, total_v):
            paginas_meta.append((reader.pages[i], item))

    if not paginas_meta:
        return BytesIO(), 0

    writer = PdfWriter()
    for page, _ in paginas_meta:
        writer.add_page(page)

    total = len(writer.pages)

    # 2) Aplicar sellos página por página
    for idx, page in enumerate(writer.pages):
        item = paginas_meta[idx][1]
        try:
            caja = page.mediabox
            x0, y0 = float(caja.left), float(caja.bottom)
            w, h = float(caja.width), float(caja.height)
        except Exception:
            x0, y0, w, h = 0, 0, 612, 792
        ctx_pg = dict(ctx, pagina=idx + 1, total=total, paso=(item.paso or ''))
        overlay = _crear_overlay(w, h, _lineas_de_sello(plantilla, item, ctx_pg))
        if overlay is None:
            continue
        try:
            if x0 or y0:
                page.merge_transformed_page(
                    overlay, Transformation().translate(x0, y0))
            else:
                page.merge_page(overlay)
        except Exception:
            pass

    buf = BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf, total
