"""Generación de reportes PDF con ReportLab, formato de encabezado FAFII."""
from datetime import datetime
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle)

AZUL_FARACH = colors.HexColor('#1B3A6B')
AZUL_MEDIO = colors.HexColor('#2E5DAC')
GRIS_CLARO = colors.HexColor('#F4F6F9')

EMPRESA = 'Laboratorios Alfa II (FARACH, S.A.)'

_estilos = getSampleStyleSheet()

ESTILO_TITULO = ParagraphStyle('TituloFAFII', parent=_estilos['Title'],
                               fontSize=13, textColor=AZUL_FARACH, leading=16)
ESTILO_EMPRESA = ParagraphStyle('Empresa', parent=_estilos['Normal'],
                                fontSize=9, textColor=colors.grey, alignment=1)
ESTILO_SECCION = ParagraphStyle('Seccion', parent=_estilos['Heading3'],
                                fontSize=11, textColor=AZUL_FARACH, spaceBefore=10)
ESTILO_NORMAL = ParagraphStyle('NormalES', parent=_estilos['Normal'], fontSize=9, leading=12)
ESTILO_CELDA = ParagraphStyle('Celda', parent=_estilos['Normal'], fontSize=8, leading=10)


def _fecha(valor):
    if not valor:
        return '—'
    if isinstance(valor, datetime):
        valor = valor.date()
    return valor.strftime('%d/%m/%Y')


def _encabezado_fafii(titulo, codigo='—', version='—', emision=None, vigencia=None):
    """Bloque de encabezado estándar FAFII: logo + título + datos de control."""
    logo = Paragraph('<b><font color="#1B3A6B" size="14">FARACH</font></b><br/>'
                     '<font size="6" color="#2E5DAC">QMS</font>', ESTILO_EMPRESA)
    cuerpo = [
        [logo, Paragraph(f'<b>{titulo}</b><br/><font size="8" color="grey">{EMPRESA}</font>',
                         ESTILO_TITULO)],
        [Paragraph(f'<b>Código:</b> {codigo}', ESTILO_CELDA),
         Table([[Paragraph(f'<b>Versión:</b> {version}', ESTILO_CELDA),
                 Paragraph(f'<b>Emisión:</b> {_fecha(emision)}', ESTILO_CELDA),
                 Paragraph(f'<b>Vigencia:</b> {_fecha(vigencia)}', ESTILO_CELDA)]],
               colWidths=[4 * cm, 4.5 * cm, 4.5 * cm])],
    ]
    tabla = Table(cuerpo, colWidths=[4 * cm, 13 * cm])
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.8, AZUL_FARACH),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_CLARO),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return tabla


def _tabla_datos(pares, ancho_etiqueta=5 * cm):
    """Tabla de dos columnas etiqueta/valor."""
    filas = [[Paragraph(f'<b>{etiqueta}</b>', ESTILO_CELDA),
              Paragraph(str(valor) if valor not in (None, '') else '—', ESTILO_CELDA)]
             for etiqueta, valor in pares]
    tabla = Table(filas, colWidths=[ancho_etiqueta, 17 * cm - ancho_etiqueta])
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ('BACKGROUND', (0, 0), (0, -1), GRIS_CLARO),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return tabla


def _tabla_listado(encabezados, filas, anchos=None):
    """Tabla tabular con encabezado azul corporativo."""
    datos = [[Paragraph(f'<b><font color="white">{e}</font></b>', ESTILO_CELDA)
              for e in encabezados]]
    for fila in filas:
        datos.append([Paragraph(str(v) if v not in (None, '') else '—', ESTILO_CELDA)
                      for v in fila])
    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    estilo = [
        ('BACKGROUND', (0, 0), (-1, 0), AZUL_FARACH),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    for i in range(2, len(datos), 2):
        estilo.append(('BACKGROUND', (0, i), (-1, i), GRIS_CLARO))
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _construir(elementos, orientacion_horizontal=False):
    buffer = BytesIO()
    tamano = letter if not orientacion_horizontal else (letter[1], letter[0])
    doc = SimpleDocTemplate(buffer, pagesize=tamano,
                            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    doc.build(elementos)
    buffer.seek(0)
    return buffer


def _pie_generacion():
    return Paragraph(
        f'<font size="7" color="grey">Generado por QMS FARACH el '
        f'{datetime.now().strftime("%d/%m/%Y %H:%M")}</font>', ESTILO_NORMAL)


# ---------------------------------------------------------------- Documentos

def pdf_ficha_documento(doc):
    elementos = [
        _encabezado_fafii('FICHA DE DOCUMENTO', doc.codigo, doc.version_actual,
                          doc.fecha_emision, doc.fecha_vigencia),
        Spacer(1, 12),
        Paragraph('Datos Generales', ESTILO_SECCION),
        _tabla_datos([
            ('Título', doc.titulo),
            ('Tipo de documento', doc.tipo_doc.nombre if doc.tipo_doc else '—'),
            ('Departamento', doc.departamento.nombre if doc.departamento else '—'),
            ('Estado', doc.estado_nombre),
            ('Versión actual', doc.version_actual),
            ('Fecha de emisión', _fecha(doc.fecha_emision)),
            ('Fecha de vigencia', _fecha(doc.fecha_vigencia)),
            ('Próxima revisión', _fecha(doc.fecha_proxima_revision)),
            ('Elaborado por', doc.elaborado_por),
            ('Revisado por', doc.revisado_por),
            ('Aprobado por', doc.aprobado_por),
            ('Ubicación física', doc.ubicacion_fisica),
            ('Copias controladas', doc.numero_copias_controladas),
        ]),
        Paragraph('Descripción y Alcance', ESTILO_SECCION),
        _tabla_datos([
            ('Descripción', doc.descripcion),
            ('Alcance', doc.alcance),
            ('Aplica a', doc.aplica_a),
        ]),
    ]
    if doc.versiones:
        elementos.append(Paragraph('Historial de Versiones', ESTILO_SECCION))
        elementos.append(_tabla_listado(
            ['Versión', 'Emisión', 'Cambios realizados', 'Aprobación'],
            [[v.numero_version, _fecha(v.fecha_emision), v.cambios_realizados,
              _fecha(v.fecha_aprobacion)] for v in doc.versiones],
            anchos=[2 * cm, 2.5 * cm, 9.5 * cm, 3 * cm]))
    elementos += [Spacer(1, 14), _pie_generacion()]
    return _construir(elementos)


def pdf_lista_maestra(documentos):
    elementos = [
        _encabezado_fafii('LISTA MAESTRA DE DOCUMENTOS'),
        Spacer(1, 12),
        _tabla_listado(
            ['Código', 'Título', 'Tipo', 'Depto.', 'Versión', 'Estado', 'Vigencia',
             'Próx. revisión'],
            [[d.codigo, d.titulo, d.tipo_doc.prefijo if d.tipo_doc else '—',
              d.departamento.codigo if d.departamento else '—', d.version_actual,
              d.estado_nombre, _fecha(d.fecha_vigencia), _fecha(d.fecha_proxima_revision)]
             for d in documentos],
            anchos=[2.2 * cm, 5.8 * cm, 1.5 * cm, 1.7 * cm, 1.7 * cm, 2.2 * cm,
                    2.5 * cm, 2.5 * cm]),
        Spacer(1, 14),
        _pie_generacion(),
    ]
    return _construir(elementos)


# ------------------------------------------------------------- Capacitación

def pdf_lista_asistencia(sesion):
    elementos = [
        _encabezado_fafii('LISTA DE ASISTENCIA — CAPACITACIÓN',
                          emision=sesion.fecha_sesion),
        Spacer(1, 12),
        _tabla_datos([
            ('Tema / Título', sesion.titulo),
            ('Fecha', _fecha(sesion.fecha_sesion)),
            ('Horario', f'{sesion.hora_inicio or "—"} a {sesion.hora_fin or "—"}'),
            ('Facilitador', sesion.facilitador),
            ('Lugar', sesion.lugar),
            ('Objetivo', sesion.objetivo),
            ('Contenido impartido', sesion.contenido_impartido),
        ]),
        Paragraph('Participantes', ESTILO_SECCION),
    ]
    filas = []
    for i, a in enumerate(sesion.asistencias, start=1):
        depto = a.participante_departamento.codigo if a.participante_departamento else '—'
        filas.append([i, a.participante_nombre, a.participante_cargo or '—', depto,
                      a.calificacion if a.calificacion is not None else '—',
                      'Sí' if a.aprobado else 'No', ''])
    # Filas en blanco para firmas adicionales
    for i in range(len(filas) + 1, len(filas) + 4):
        filas.append([i, '', '', '', '', '', ''])
    elementos.append(_tabla_listado(
        ['No.', 'Nombre del participante', 'Cargo', 'Depto.', 'Calif.', 'Aprob.', 'Firma'],
        filas,
        anchos=[1 * cm, 5 * cm, 3.5 * cm, 1.8 * cm, 1.5 * cm, 1.7 * cm, 3.5 * cm]))
    elementos += [
        Spacer(1, 24),
        Table([[Paragraph('_______________________<br/>Firma del Facilitador', ESTILO_CELDA),
                Paragraph('_______________________<br/>Garantía de Calidad', ESTILO_CELDA)]],
              colWidths=[8.5 * cm, 8.5 * cm]),
        Spacer(1, 14),
        _pie_generacion(),
    ]
    return _construir(elementos)


def pdf_disclosure(documento, cargo, registros):
    elementos = [
        _encabezado_fafii('FORMULARIO DE DISCLOSURE — ENTRENAMIENTO EN DOCUMENTO',
                          documento.codigo if documento else '—',
                          documento.version_actual if documento else '—',
                          documento.fecha_emision if documento else None,
                          documento.fecha_vigencia if documento else None),
        Spacer(1, 12),
        _tabla_datos([
            ('Documento', f'{documento.codigo} — {documento.titulo}' if documento else '—'),
            ('Cargo / Posición', cargo or 'Todos'),
        ]),
        Paragraph(
            'Declaro que he leído, entendido y recibido entrenamiento sobre el documento '
            'indicado, y me comprometo a cumplirlo en el desempeño de mis funciones.',
            ESTILO_NORMAL),
        Spacer(1, 8),
        _tabla_listado(
            ['No.', 'Nombre del empleado', 'Cargo', 'Fecha entren.', 'Entrenado por', 'Firma'],
            [[i, r.empleado_nombre, r.cargo, _fecha(r.fecha_entrenamiento),
              r.entrenado_por or '—', 'Firmado' if r.firmo_disclosure else '']
             for i, r in enumerate(registros, start=1)] or [['1', '', '', '', '', '']],
            anchos=[1 * cm, 5 * cm, 3.5 * cm, 2.5 * cm, 3 * cm, 3 * cm]),
        Spacer(1, 14),
        _pie_generacion(),
    ]
    return _construir(elementos)


# --------------------------------------------------------------------- CAPA

def pdf_capa(capa):
    elementos = [
        _encabezado_fafii('INFORME DE CAPA', capa.numero_capa,
                          emision=capa.fecha_apertura),
        Spacer(1, 12),
        Paragraph('Identificación', ESTILO_SECCION),
        _tabla_datos([
            ('Número CAPA', capa.numero_capa),
            ('Título', capa.titulo),
            ('Tipo', capa.tipo),
            ('Origen', capa.origen),
            ('Prioridad', capa.prioridad),
            ('Estado', capa.estado_nombre),
            ('Área afectada', capa.area_afectada),
            ('Departamento', capa.departamento.nombre if capa.departamento else '—'),
            ('Responsable', capa.responsable.nombre_completo if capa.responsable else '—'),
            ('Fecha apertura', _fecha(capa.fecha_apertura)),
            ('Fecha límite', _fecha(capa.fecha_limite_implementacion)),
        ]),
        Paragraph('Descripción del Problema', ESTILO_SECCION),
        _tabla_datos([
            ('Hallazgo', capa.descripcion_hallazgo),
            ('Problema', capa.descripcion_problema),
        ]),
        Paragraph('Análisis de Causa Raíz', ESTILO_SECCION),
        _tabla_datos([
            ('Método de análisis', capa.metodo_analisis),
            ('Causa raíz identificada', capa.causa_raiz_identificada),
        ]),
        Paragraph('Plan de Acción', ESTILO_SECCION),
        _tabla_datos([
            ('Acciones correctivas', capa.acciones_correctivas),
            ('Recursos necesarios', capa.recursos_necesarios),
        ]),
    ]
    if capa.acciones:
        elementos.append(Paragraph('Acciones Específicas', ESTILO_SECCION))
        elementos.append(_tabla_listado(
            ['Acción', 'Responsable', 'Fecha límite', 'Estado', 'Completada'],
            [[a.descripcion_accion,
              a.responsable.nombre_completo if a.responsable else '—',
              _fecha(a.fecha_limite), a.estado, _fecha(a.fecha_completada)]
             for a in capa.acciones],
            anchos=[6.5 * cm, 4 * cm, 2.5 * cm, 2 * cm, 2.5 * cm]))
    elementos += [
        Paragraph('Implementación y Cierre', ESTILO_SECCION),
        _tabla_datos([
            ('Evidencia de implementación', capa.evidencia_implementacion),
            ('Fecha implementación', _fecha(capa.fecha_implementacion)),
            ('Verificado por',
             capa.verificado_por.nombre_completo if capa.verificado_por else '—'),
            ('Efectividad verificada', 'Sí' if capa.efectividad_verificada else 'No'),
            ('Comentario de cierre', capa.comentario_cierre),
            ('Fecha de cierre', _fecha(capa.fecha_cierre)),
        ]),
        Spacer(1, 14),
        _pie_generacion(),
    ]
    return _construir(elementos)


# ---------------------------------------------------------------- Auditoría

def pdf_auditoria(aud):
    elementos = [
        _encabezado_fafii('INFORME DE AUDITORÍA', aud.numero_auditoria,
                          emision=aud.fecha_inicio),
        Spacer(1, 12),
        Paragraph('Datos de la Auditoría', ESTILO_SECCION),
        _tabla_datos([
            ('Número', aud.numero_auditoria),
            ('Título', aud.titulo),
            ('Tipo', aud.tipo),
            ('Estado', aud.estado_nombre),
            ('Alcance', aud.alcance),
            ('Objetivo', aud.objetivo),
            ('Fecha inicio', _fecha(aud.fecha_inicio)),
            ('Fecha fin planificada', _fecha(aud.fecha_fin_planificada)),
            ('Auditor líder', aud.auditor_lider),
            ('Equipo auditor', aud.equipo_auditor),
            ('Departamentos auditados', aud.departamentos_auditados),
            ('Fecha informe', _fecha(aud.fecha_informe)),
            ('Resumen ejecutivo', aud.resumen_ejecutivo),
        ]),
    ]
    if aud.hallazgos:
        elementos.append(Paragraph('Hallazgos', ESTILO_SECCION))
        elementos.append(_tabla_listado(
            ['Tipo', 'Descripción', 'Requisito', 'CAPA', 'Estado'],
            [[h.tipo_nombre, h.descripcion, h.requisito_incumplido or '—',
              h.capa_generada.numero_capa if h.capa_generada else '—', h.estado]
             for h in aud.hallazgos],
            anchos=[3.2 * cm, 6.5 * cm, 3.3 * cm, 2.5 * cm, 2 * cm]))
    elementos += [Spacer(1, 14), _pie_generacion()]
    return _construir(elementos)


# ------------------------------------------------------ Solicitud de cambio

def pdf_solicitud_cambio(sc):
    elementos = [
        _encabezado_fafii('SOLICITUD DE CAMBIO', sc.numero_sc,
                          emision=sc.fecha_solicitud),
        Spacer(1, 12),
        Paragraph('Solicitud', ESTILO_SECCION),
        _tabla_datos([
            ('Número SC', sc.numero_sc),
            ('Título', sc.titulo),
            ('Tipo de cambio', sc.tipo_cambio),
            ('Estado', sc.estado_nombre),
            ('Área afectada', sc.area_afectada),
            ('Documento afectado',
             sc.documento_afectado.codigo if sc.documento_afectado else '—'),
            ('Solicitado por',
             sc.solicitado_por.nombre_completo if sc.solicitado_por else '—'),
            ('Fecha solicitud', _fecha(sc.fecha_solicitud)),
            ('Descripción del cambio', sc.descripcion_cambio),
            ('Justificación', sc.justificacion),
            ('Impacto estimado', sc.impacto_estimado),
        ]),
        Paragraph('Evaluación', ESTILO_SECCION),
        _tabla_datos([
            ('Evaluado por', sc.evaluado_por.nombre_completo if sc.evaluado_por else '—'),
            ('Fecha evaluación', _fecha(sc.fecha_evaluacion)),
            ('Decisión', sc.decision),
            ('Comentario', sc.comentario_evaluacion),
        ]),
        Paragraph('Implementación y Cierre', ESTILO_SECCION),
        _tabla_datos([
            ('Implementado por',
             sc.implementado_por.nombre_completo if sc.implementado_por else '—'),
            ('Fecha implementación', _fecha(sc.fecha_implementacion)),
            ('Evidencia', sc.evidencia_implementacion),
            ('Cerrado por', sc.cerrado_por.nombre_completo if sc.cerrado_por else '—'),
            ('Fecha cierre', _fecha(sc.fecha_cierre)),
        ]),
        Spacer(1, 14),
        _pie_generacion(),
    ]
    return _construir(elementos)
