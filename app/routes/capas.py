"""Módulo 4 — CAPA (Acciones Correctivas y Preventivas)."""
from datetime import date
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, send_file, current_app)
from flask_login import login_required, current_user
from app.extensions import db
from app.models.capa import (CAPA, AccionCAPA, TIPOS_CAPA, ORIGENES_CAPA,
                             PRIORIDADES_CAPA, ESTADOS_CAPA)
from app.models.user import Usuario
from app.models.config_app import Departamento
from app.utils.decorators import rol_requerido
from app.utils.helpers import parse_fecha, registrar_log, generar_numero
from app.services import pdf_service, excel_service

capas_bp = Blueprint('capas', __name__)


def _filtrar():
    consulta = CAPA.query
    estado = request.args.get('estado', '')
    tipo = request.args.get('tipo', '')
    depto = request.args.get('departamento', type=int)
    busqueda = request.args.get('q', '').strip()
    if estado:
        consulta = consulta.filter(CAPA.estado == estado)
    if tipo:
        consulta = consulta.filter(CAPA.tipo == tipo)
    if depto:
        consulta = consulta.filter(CAPA.departamento_id == depto)
    if busqueda:
        like = f'%{busqueda}%'
        consulta = consulta.filter(db.or_(CAPA.numero_capa.ilike(like),
                                          CAPA.titulo.ilike(like)))
    return consulta.order_by(CAPA.numero_capa.desc())


def _contexto():
    return {
        'tipos': TIPOS_CAPA,
        'origenes': ORIGENES_CAPA,
        'prioridades': PRIORIDADES_CAPA,
        'estados': ESTADOS_CAPA,
        'departamentos': Departamento.query.filter_by(activo=True)
                                           .order_by(Departamento.codigo).all(),
        'usuarios': Usuario.query.filter_by(activo=True)
                                 .order_by(Usuario.nombre_completo).all(),
    }


@capas_bp.route('/')
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def lista():
    pagina = request.args.get('pagina', 1, type=int)
    paginacion = _filtrar().paginate(
        page=pagina, per_page=current_app.config['REGISTROS_POR_PAGINA'], error_out=False)
    hoy = date.today()
    resumen = {
        'abiertas': CAPA.query.filter(CAPA.estado.notin_(['CERRADA'])).count(),
        'vencidas': CAPA.query.filter(CAPA.estado.notin_(['CERRADA']),
                                      CAPA.fecha_limite_implementacion.isnot(None),
                                      CAPA.fecha_limite_implementacion < hoy).count(),
        'cerradas': CAPA.query.filter_by(estado='CERRADA').count(),
    }
    return render_template('capas/lista.html', paginacion=paginacion,
                           capas=paginacion.items, resumen=resumen, hoy=hoy,
                           **_contexto())


@capas_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def nueva():
    if request.method == 'POST':
        capa = CAPA(
            numero_capa=generar_numero(CAPA, 'numero_capa', 'CAPA'),
            tipo=request.form.get('tipo', 'CORRECTIVA'),
            origen=request.form.get('origen', 'OTRO'),
            titulo=request.form.get('titulo', '').strip(),
            descripcion_hallazgo=request.form.get('descripcion_hallazgo', '').strip(),
            descripcion_problema=request.form.get('descripcion_problema', '').strip(),
            area_afectada=request.form.get('area_afectada', '').strip(),
            departamento_id=request.form.get('departamento_id', type=int) or None,
            responsable_id=request.form.get('responsable_id', type=int) or None,
            fecha_apertura=date.today(),
            fecha_limite_implementacion=parse_fecha(
                request.form.get('fecha_limite_implementacion')),
            prioridad=request.form.get('prioridad', 'MEDIA'),
            creado_por_id=current_user.id,
        )
        db.session.add(capa)
        db.session.commit()
        registrar_log('CREACION', 'CAPA', f'{capa.numero_capa} creada')
        flash(f'CAPA {capa.numero_capa} creada.', 'success')
        return redirect(url_for('capas.detalle', id=capa.id))

    return render_template('capas/form.html', capa=None, **_contexto())


@capas_bp.route('/<int:id>')
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def detalle(id):
    capa = db.get_or_404(CAPA, id)
    return render_template('capas/detalle.html', capa=capa, hoy=date.today(),
                           **_contexto())


@capas_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def editar(id):
    capa = db.get_or_404(CAPA, id)
    if request.method == 'POST':
        capa.tipo = request.form.get('tipo', capa.tipo)
        capa.origen = request.form.get('origen', capa.origen)
        capa.titulo = request.form.get('titulo', '').strip()
        capa.descripcion_hallazgo = request.form.get('descripcion_hallazgo', '').strip()
        capa.descripcion_problema = request.form.get('descripcion_problema', '').strip()
        capa.area_afectada = request.form.get('area_afectada', '').strip()
        capa.departamento_id = request.form.get('departamento_id', type=int) or None
        capa.responsable_id = request.form.get('responsable_id', type=int) or None
        capa.fecha_limite_implementacion = parse_fecha(
            request.form.get('fecha_limite_implementacion'))
        capa.prioridad = request.form.get('prioridad', capa.prioridad)
        db.session.commit()
        registrar_log('EDICION', 'CAPA', f'{capa.numero_capa} editada')
        flash('CAPA actualizada.', 'success')
        return redirect(url_for('capas.detalle', id=capa.id))

    return render_template('capas/form.html', capa=capa, **_contexto())


@capas_bp.route('/<int:id>/analisis', methods=['POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def analisis(id):
    capa = db.get_or_404(CAPA, id)
    capa.metodo_analisis = request.form.get('metodo_analisis', '').strip()
    capa.causa_raiz_identificada = request.form.get('causa_raiz_identificada', '').strip()
    capa.acciones_correctivas = request.form.get('acciones_correctivas', '').strip()
    capa.recursos_necesarios = request.form.get('recursos_necesarios', '').strip()
    if capa.estado == 'ABIERTA':
        capa.estado = 'EN_PROCESO'
    db.session.commit()
    registrar_log('EDICION', 'CAPA', f'{capa.numero_capa}: análisis de causa raíz')
    flash('Análisis de causa raíz y plan de acción guardados.', 'success')
    return redirect(url_for('capas.detalle', id=id))


@capas_bp.route('/<int:id>/acciones/nueva', methods=['POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def nueva_accion(id):
    capa = db.get_or_404(CAPA, id)
    descripcion = request.form.get('descripcion_accion', '').strip()
    if descripcion:
        db.session.add(AccionCAPA(
            capa_id=capa.id,
            descripcion_accion=descripcion,
            responsable_id=request.form.get('responsable_id', type=int) or None,
            fecha_limite=parse_fecha(request.form.get('fecha_limite')),
        ))
        db.session.commit()
        flash('Acción agregada.', 'success')
    return redirect(url_for('capas.detalle', id=id))


@capas_bp.route('/acciones/<int:id>/completar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def completar_accion(id):
    accion = db.get_or_404(AccionCAPA, id)
    accion.estado = 'COMPLETADA'
    accion.fecha_completada = date.today()
    accion.evidencia = request.form.get('evidencia', '').strip()
    db.session.commit()
    flash('Acción marcada como completada.', 'success')
    return redirect(url_for('capas.detalle', id=accion.capa_id))


@capas_bp.route('/<int:id>/implementar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def implementar(id):
    capa = db.get_or_404(CAPA, id)
    capa.evidencia_implementacion = request.form.get('evidencia_implementacion', '').strip()
    capa.implementado_por_id = current_user.id
    capa.fecha_implementacion = parse_fecha(
        request.form.get('fecha_implementacion')) or date.today()
    capa.estado = 'VERIFICACION'
    db.session.commit()
    registrar_log('IMPLEMENTACION', 'CAPA', f'{capa.numero_capa} implementada')
    flash('Implementación registrada. La CAPA pasó a verificación.', 'success')
    return redirect(url_for('capas.detalle', id=id))


@capas_bp.route('/<int:id>/cerrar', methods=['POST'])
@login_required
@rol_requerido('aprobador')
def cerrar(id):
    capa = db.get_or_404(CAPA, id)
    capa.verificado_por_id = current_user.id
    capa.fecha_verificacion = date.today()
    capa.efectividad_verificada = bool(request.form.get('efectividad_verificada'))
    capa.comentario_cierre = request.form.get('comentario_cierre', '').strip()
    capa.fecha_cierre = date.today()
    capa.cerrado_por_id = current_user.id
    capa.estado = 'CERRADA'
    db.session.commit()
    registrar_log('CIERRE', 'CAPA', f'{capa.numero_capa} cerrada')
    flash(f'CAPA {capa.numero_capa} verificada y cerrada.', 'success')
    return redirect(url_for('capas.detalle', id=id))


@capas_bp.route('/exportar/excel')
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def exportar_excel():
    capas = _filtrar().all()
    filas = [[c.numero_capa, c.titulo, c.tipo, c.origen, c.prioridad,
              c.estado_nombre,
              c.departamento.nombre if c.departamento else '',
              c.responsable.nombre_completo if c.responsable else '',
              c.fecha_apertura.strftime('%d/%m/%Y') if c.fecha_apertura else '',
              c.fecha_limite_implementacion.strftime('%d/%m/%Y')
              if c.fecha_limite_implementacion else '',
              c.fecha_cierre.strftime('%d/%m/%Y') if c.fecha_cierre else '',
              'Sí' if c.esta_vencida else 'No']
             for c in capas]
    archivo = excel_service.exportar_excel(
        'Listado de CAPAs', 'CAPAs',
        ['Número', 'Título', 'Tipo', 'Origen', 'Prioridad', 'Estado', 'Departamento',
         'Responsable', 'F. Apertura', 'F. Límite', 'F. Cierre', 'Vencida'],
        filas)
    registrar_log('EXPORTACION', 'CAPA', 'Listado exportado a Excel')
    return send_file(archivo, as_attachment=True, download_name='capas.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@capas_bp.route('/<int:id>/pdf')
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def reporte_pdf(id):
    capa = db.get_or_404(CAPA, id)
    archivo = pdf_service.pdf_capa(capa)
    return send_file(archivo, as_attachment=True,
                     download_name=f'{capa.numero_capa}.pdf', mimetype='application/pdf')
