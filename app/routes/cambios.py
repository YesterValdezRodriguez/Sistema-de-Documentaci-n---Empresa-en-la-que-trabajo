"""Módulo 2 — Control de Cambios."""
from datetime import date
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, send_file, current_app)
from flask_login import login_required, current_user
from app.extensions import db
from app.models.cambio import (SolicitudCambio, ComentarioCambio, ESTADOS_SC,
                               TIPOS_CAMBIO)
from app.models.documento import Documento
from app.models.config_app import Departamento
from app.utils.decorators import rol_requerido
from app.utils.helpers import parse_fecha, registrar_log, generar_numero
from app.services import pdf_service, excel_service

cambios_bp = Blueprint('cambios', __name__)


def _filtrar():
    consulta = SolicitudCambio.query
    estado = request.args.get('estado', '')
    tipo = request.args.get('tipo', '')
    area = request.args.get('area', '').strip()
    if estado:
        consulta = consulta.filter(SolicitudCambio.estado == estado)
    if tipo:
        consulta = consulta.filter(SolicitudCambio.tipo_cambio == tipo)
    if area:
        consulta = consulta.filter(SolicitudCambio.area_afectada.ilike(f'%{area}%'))
    return consulta.order_by(SolicitudCambio.numero_sc.desc())


@cambios_bp.route('/')
@login_required
def lista():
    pagina = request.args.get('pagina', 1, type=int)
    paginacion = _filtrar().paginate(
        page=pagina, per_page=current_app.config['REGISTROS_POR_PAGINA'], error_out=False)
    resumen = {
        'abiertas': SolicitudCambio.query.filter_by(estado='ABIERTA').count(),
        'en_evaluacion': SolicitudCambio.query.filter_by(estado='EN_EVALUACION').count(),
        'por_cerrar': SolicitudCambio.query.filter(
            SolicitudCambio.estado.in_(['APROBADA', 'IMPLEMENTADA'])).count(),
    }
    return render_template('cambios/lista.html', paginacion=paginacion,
                           solicitudes=paginacion.items, estados=ESTADOS_SC,
                           tipos=TIPOS_CAMBIO, resumen=resumen)


@cambios_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def nueva():
    if request.method == 'POST':
        sc = SolicitudCambio(
            numero_sc=generar_numero(SolicitudCambio, 'numero_sc', 'SC'),
            titulo=request.form.get('titulo', '').strip(),
            tipo_cambio=request.form.get('tipo_cambio', 'Otro'),
            descripcion_cambio=request.form.get('descripcion_cambio', '').strip(),
            justificacion=request.form.get('justificacion', '').strip(),
            impacto_estimado=request.form.get('impacto_estimado', '').strip(),
            documento_afectado_id=request.form.get('documento_afectado_id', type=int) or None,
            area_afectada=request.form.get('area_afectada', '').strip(),
            solicitado_por_id=current_user.id,
            fecha_solicitud=date.today(),
        )
        db.session.add(sc)
        db.session.commit()
        registrar_log('CREACION', 'Cambios', f'Solicitud {sc.numero_sc} creada')
        flash(f'Solicitud de cambio {sc.numero_sc} creada.', 'success')
        return redirect(url_for('cambios.detalle', id=sc.id))

    documentos = Documento.query.filter_by(activo=True).order_by(Documento.codigo).all()
    return render_template('cambios/form.html', tipos=TIPOS_CAMBIO, documentos=documentos)


@cambios_bp.route('/<int:id>')
@login_required
def detalle(id):
    sc = db.get_or_404(SolicitudCambio, id)
    return render_template('cambios/detalle.html', sc=sc)


@cambios_bp.route('/<int:id>/evaluar', methods=['POST'])
@login_required
@rol_requerido('aprobador')
def evaluar(id):
    sc = db.get_or_404(SolicitudCambio, id)
    if sc.estado not in ('ABIERTA', 'EN_EVALUACION'):
        flash('La solicitud no está en un estado evaluable.', 'warning')
        return redirect(url_for('cambios.detalle', id=id))

    decision = request.form.get('decision')
    sc.evaluado_por_id = current_user.id
    sc.fecha_evaluacion = date.today()
    sc.comentario_evaluacion = request.form.get('comentario_evaluacion', '').strip()
    if decision == 'APROBAR':
        sc.estado = 'APROBADA'
        sc.decision = 'APROBADA'
        flash(f'Solicitud {sc.numero_sc} aprobada.', 'success')
    elif decision == 'RECHAZAR':
        sc.estado = 'RECHAZADA'
        sc.decision = 'RECHAZADA'
        flash(f'Solicitud {sc.numero_sc} rechazada.', 'info')
    else:
        sc.estado = 'EN_EVALUACION'
        flash(f'Solicitud {sc.numero_sc} marcada en evaluación.', 'info')
    db.session.commit()
    registrar_log('EVALUACION', 'Cambios', f'{sc.numero_sc}: {sc.estado}')
    return redirect(url_for('cambios.detalle', id=id))


@cambios_bp.route('/<int:id>/implementar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def implementar(id):
    sc = db.get_or_404(SolicitudCambio, id)
    if sc.estado != 'APROBADA':
        flash('Solo las solicitudes aprobadas pueden implementarse.', 'warning')
        return redirect(url_for('cambios.detalle', id=id))
    sc.estado = 'IMPLEMENTADA'
    sc.implementado_por_id = current_user.id
    sc.fecha_implementacion = parse_fecha(request.form.get('fecha_implementacion')) or date.today()
    sc.evidencia_implementacion = request.form.get('evidencia_implementacion', '').strip()
    db.session.commit()
    registrar_log('IMPLEMENTACION', 'Cambios', f'{sc.numero_sc} implementada')
    flash(f'Solicitud {sc.numero_sc} marcada como implementada.', 'success')
    return redirect(url_for('cambios.detalle', id=id))


@cambios_bp.route('/<int:id>/cerrar', methods=['POST'])
@login_required
@rol_requerido('aprobador')
def cerrar(id):
    sc = db.get_or_404(SolicitudCambio, id)
    if sc.estado not in ('IMPLEMENTADA', 'RECHAZADA'):
        flash('Solo solicitudes implementadas o rechazadas pueden cerrarse.', 'warning')
        return redirect(url_for('cambios.detalle', id=id))
    sc.estado = 'CERRADA'
    sc.cerrado_por_id = current_user.id
    sc.fecha_cierre = date.today()
    db.session.commit()
    registrar_log('CIERRE', 'Cambios', f'{sc.numero_sc} cerrada')
    flash(f'Solicitud {sc.numero_sc} cerrada formalmente.', 'success')
    return redirect(url_for('cambios.detalle', id=id))


@cambios_bp.route('/<int:id>/comentar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def comentar(id):
    sc = db.get_or_404(SolicitudCambio, id)
    texto = request.form.get('comentario', '').strip()
    if texto:
        db.session.add(ComentarioCambio(solicitud_id=sc.id, usuario_id=current_user.id,
                                        comentario=texto))
        db.session.commit()
        flash('Comentario agregado.', 'success')
    return redirect(url_for('cambios.detalle', id=id))


@cambios_bp.route('/exportar/excel')
@login_required
def exportar_excel():
    solicitudes = _filtrar().all()
    filas = [[s.numero_sc, s.titulo, s.tipo_cambio, s.area_afectada or '',
              s.documento_afectado.codigo if s.documento_afectado else '',
              s.estado_nombre,
              s.solicitado_por.nombre_completo if s.solicitado_por else '',
              s.fecha_solicitud.strftime('%d/%m/%Y') if s.fecha_solicitud else '',
              s.fecha_evaluacion.strftime('%d/%m/%Y') if s.fecha_evaluacion else '',
              s.fecha_implementacion.strftime('%d/%m/%Y') if s.fecha_implementacion else '',
              s.fecha_cierre.strftime('%d/%m/%Y') if s.fecha_cierre else '']
             for s in solicitudes]
    archivo = excel_service.exportar_excel(
        'Solicitudes de Cambio', 'Control de Cambios',
        ['Número', 'Título', 'Tipo', 'Área', 'Documento', 'Estado', 'Solicitado por',
         'F. Solicitud', 'F. Evaluación', 'F. Implementación', 'F. Cierre'],
        filas)
    registrar_log('EXPORTACION', 'Cambios', 'Solicitudes exportadas a Excel')
    return send_file(archivo, as_attachment=True,
                     download_name='solicitudes_cambio.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@cambios_bp.route('/<int:id>/pdf')
@login_required
def reporte_pdf(id):
    sc = db.get_or_404(SolicitudCambio, id)
    archivo = pdf_service.pdf_solicitud_cambio(sc)
    return send_file(archivo, as_attachment=True,
                     download_name=f'{sc.numero_sc}.pdf', mimetype='application/pdf')
