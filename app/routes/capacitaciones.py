"""Módulo 3 — Capacitación y Entrenamiento."""
from datetime import date, timedelta
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, send_file, current_app)
from flask_login import login_required, current_user
from app.extensions import db
from app.models.capacitacion import (PlanCapacitacion, SesionCapacitacion,
                                     AsistenciaCapacitacion, RegistroEntrenamiento,
                                     TIPOS_PLAN, ESTADOS_SESION)
from app.models.documento import Documento
from app.models.config_app import Departamento, CargoPosicion
from app.utils.decorators import rol_requerido
from app.utils.helpers import parse_fecha, registrar_log
from app.services import pdf_service, excel_service

capacitaciones_bp = Blueprint('capacitaciones', __name__)


def _contexto():
    return {
        'tipos': TIPOS_PLAN,
        'departamentos': Departamento.query.filter_by(activo=True)
                                           .order_by(Departamento.codigo).all(),
        'documentos': Documento.query.filter_by(activo=True)
                                     .order_by(Documento.codigo).all(),
        'cargos': CargoPosicion.query.filter_by(activo=True)
                                     .order_by(CargoPosicion.nombre).all(),
    }


# ------------------------------------------------------------------- Planes

@capacitaciones_bp.route('/')
@login_required
def planes():
    pagina = request.args.get('pagina', 1, type=int)
    consulta = PlanCapacitacion.query
    depto = request.args.get('departamento', type=int)
    tipo = request.args.get('tipo', '')
    if depto:
        consulta = consulta.filter_by(departamento_id=depto)
    if tipo:
        consulta = consulta.filter_by(tipo=tipo)
    paginacion = consulta.order_by(PlanCapacitacion.titulo).paginate(
        page=pagina, per_page=current_app.config['REGISTROS_POR_PAGINA'], error_out=False)

    # Alertas: planes con frecuencia cuya última sesión realizada ya venció
    hoy = date.today()
    alertas = []
    for plan in PlanCapacitacion.query.filter(PlanCapacitacion.activo.is_(True),
                                              PlanCapacitacion.frecuencia_meses > 0).all():
        ultima = (SesionCapacitacion.query
                  .filter_by(plan_id=plan.id, estado='REALIZADA')
                  .order_by(SesionCapacitacion.fecha_sesion.desc()).first())
        if ultima:
            vencimiento = ultima.fecha_sesion + timedelta(days=plan.frecuencia_meses * 30)
            if vencimiento <= hoy + timedelta(days=30):
                alertas.append((plan, ultima.fecha_sesion, vencimiento))
        else:
            alertas.append((plan, None, None))

    return render_template('capacitaciones/planes.html', paginacion=paginacion,
                           planes=paginacion.items, alertas=alertas, hoy=hoy,
                           **_contexto())


@capacitaciones_bp.route('/planes/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def nuevo_plan():
    if request.method == 'POST':
        plan = PlanCapacitacion(
            titulo=request.form.get('titulo', '').strip(),
            descripcion=request.form.get('descripcion', '').strip(),
            tipo=request.form.get('tipo', 'puntual'),
            documento_id=request.form.get('documento_id', type=int) or None,
            cargo_aplica=request.form.get('cargo_aplica', '').strip(),
            departamento_id=request.form.get('departamento_id', type=int) or None,
            frecuencia_meses=request.form.get('frecuencia_meses', type=int) or 0,
        )
        db.session.add(plan)
        db.session.commit()
        registrar_log('CREACION', 'Capacitaciones', f'Plan "{plan.titulo}" creado')
        flash('Plan de capacitación creado.', 'success')
        return redirect(url_for('capacitaciones.planes'))
    return render_template('capacitaciones/plan_form.html', plan=None, **_contexto())


@capacitaciones_bp.route('/planes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def editar_plan(id):
    plan = db.get_or_404(PlanCapacitacion, id)
    if request.method == 'POST':
        plan.titulo = request.form.get('titulo', '').strip()
        plan.descripcion = request.form.get('descripcion', '').strip()
        plan.tipo = request.form.get('tipo', plan.tipo)
        plan.documento_id = request.form.get('documento_id', type=int) or None
        plan.cargo_aplica = request.form.get('cargo_aplica', '').strip()
        plan.departamento_id = request.form.get('departamento_id', type=int) or None
        plan.frecuencia_meses = request.form.get('frecuencia_meses', type=int) or 0
        plan.activo = bool(request.form.get('activo'))
        db.session.commit()
        registrar_log('EDICION', 'Capacitaciones', f'Plan "{plan.titulo}" editado')
        flash('Plan actualizado.', 'success')
        return redirect(url_for('capacitaciones.planes'))
    return render_template('capacitaciones/plan_form.html', plan=plan, **_contexto())


# ----------------------------------------------------------------- Sesiones

@capacitaciones_bp.route('/sesiones')
@login_required
def sesiones():
    pagina = request.args.get('pagina', 1, type=int)
    consulta = SesionCapacitacion.query
    estado = request.args.get('estado', '')
    if estado:
        consulta = consulta.filter_by(estado=estado)
    paginacion = consulta.order_by(SesionCapacitacion.fecha_sesion.desc()).paginate(
        page=pagina, per_page=current_app.config['REGISTROS_POR_PAGINA'], error_out=False)
    return render_template('capacitaciones/sesiones.html', paginacion=paginacion,
                           sesiones=paginacion.items, estados=ESTADOS_SESION)


@capacitaciones_bp.route('/sesiones/nueva', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def nueva_sesion():
    if request.method == 'POST':
        sesion = SesionCapacitacion(
            plan_id=request.form.get('plan_id', type=int) or None,
            titulo=request.form.get('titulo', '').strip(),
            fecha_sesion=parse_fecha(request.form.get('fecha_sesion')) or date.today(),
            hora_inicio=request.form.get('hora_inicio', '').strip(),
            hora_fin=request.form.get('hora_fin', '').strip(),
            facilitador=request.form.get('facilitador', '').strip(),
            lugar=request.form.get('lugar', '').strip(),
            objetivo=request.form.get('objetivo', '').strip(),
            creado_por_id=current_user.id,
        )
        db.session.add(sesion)
        db.session.commit()
        registrar_log('CREACION', 'Capacitaciones', f'Sesión "{sesion.titulo}" programada')
        flash('Sesión programada.', 'success')
        return redirect(url_for('capacitaciones.detalle_sesion', id=sesion.id))
    planes_activos = PlanCapacitacion.query.filter_by(activo=True)\
        .order_by(PlanCapacitacion.titulo).all()
    return render_template('capacitaciones/sesion_form.html', sesion=None,
                           planes=planes_activos)


@capacitaciones_bp.route('/sesiones/<int:id>')
@login_required
def detalle_sesion(id):
    sesion = db.get_or_404(SesionCapacitacion, id)
    departamentos = Departamento.query.filter_by(activo=True)\
        .order_by(Departamento.codigo).all()
    return render_template('capacitaciones/sesion_detalle.html', sesion=sesion,
                           departamentos=departamentos)


@capacitaciones_bp.route('/sesiones/<int:id>/asistentes/agregar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def agregar_asistente(id):
    sesion = db.get_or_404(SesionCapacitacion, id)
    nombre = request.form.get('participante_nombre', '').strip()
    if nombre:
        calificacion = request.form.get('calificacion', type=int)
        db.session.add(AsistenciaCapacitacion(
            sesion_id=sesion.id,
            participante_nombre=nombre,
            participante_cargo=request.form.get('participante_cargo', '').strip(),
            participante_departamento_id=request.form.get(
                'participante_departamento_id', type=int) or None,
            firmo=bool(request.form.get('firmo')),
            calificacion=calificacion,
            aprobado=(calificacion is not None and calificacion >= 70),
        ))
        db.session.commit()
        flash('Participante agregado.', 'success')
    return redirect(url_for('capacitaciones.detalle_sesion', id=id))


@capacitaciones_bp.route('/asistentes/<int:id>/eliminar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def eliminar_asistente(id):
    asistencia = db.get_or_404(AsistenciaCapacitacion, id)
    sesion_id = asistencia.sesion_id
    db.session.delete(asistencia)
    db.session.commit()
    flash('Participante eliminado.', 'success')
    return redirect(url_for('capacitaciones.detalle_sesion', id=sesion_id))


@capacitaciones_bp.route('/sesiones/<int:id>/realizar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def realizar_sesion(id):
    sesion = db.get_or_404(SesionCapacitacion, id)
    sesion.estado = 'REALIZADA'
    sesion.contenido_impartido = request.form.get('contenido_impartido', '').strip()
    sesion.hora_fin = request.form.get('hora_fin', sesion.hora_fin)
    db.session.commit()
    registrar_log('EDICION', 'Capacitaciones', f'Sesión "{sesion.titulo}" realizada')
    flash('Sesión marcada como realizada.', 'success')
    return redirect(url_for('capacitaciones.detalle_sesion', id=id))


@capacitaciones_bp.route('/sesiones/<int:id>/cancelar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def cancelar_sesion(id):
    sesion = db.get_or_404(SesionCapacitacion, id)
    sesion.estado = 'CANCELADA'
    db.session.commit()
    registrar_log('EDICION', 'Capacitaciones', f'Sesión "{sesion.titulo}" cancelada')
    flash('Sesión cancelada.', 'info')
    return redirect(url_for('capacitaciones.detalle_sesion', id=id))


@capacitaciones_bp.route('/sesiones/<int:id>/asistencia/pdf')
@login_required
def asistencia_pdf(id):
    sesion = db.get_or_404(SesionCapacitacion, id)
    archivo = pdf_service.pdf_lista_asistencia(sesion)
    return send_file(archivo, as_attachment=True,
                     download_name=f'asistencia_sesion_{sesion.id}.pdf',
                     mimetype='application/pdf')


# ------------------------------------------------ Registros de entrenamiento

@capacitaciones_bp.route('/entrenamientos')
@login_required
def entrenamientos():
    pagina = request.args.get('pagina', 1, type=int)
    consulta = RegistroEntrenamiento.query
    doc_id = request.args.get('documento_id', type=int)
    depto = request.args.get('departamento', type=int)
    if doc_id:
        consulta = consulta.filter_by(documento_id=doc_id)
    if depto:
        consulta = consulta.filter_by(departamento_id=depto)
    paginacion = consulta.order_by(RegistroEntrenamiento.fecha_entrenamiento.desc())\
        .paginate(page=pagina, per_page=current_app.config['REGISTROS_POR_PAGINA'],
                  error_out=False)
    return render_template('capacitaciones/entrenamientos.html', paginacion=paginacion,
                           registros=paginacion.items, **_contexto())


@capacitaciones_bp.route('/entrenamientos/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def nuevo_entrenamiento():
    if request.method == 'POST':
        registro = RegistroEntrenamiento(
            cargo=request.form.get('cargo', '').strip(),
            departamento_id=request.form.get('departamento_id', type=int) or None,
            documento_id=request.form.get('documento_id', type=int),
            empleado_nombre=request.form.get('empleado_nombre', '').strip(),
            fecha_entrenamiento=parse_fecha(request.form.get('fecha_entrenamiento')),
            entrenado_por=request.form.get('entrenado_por', '').strip(),
            firmo_disclosure=bool(request.form.get('firmo_disclosure')),
            fecha_firma=parse_fecha(request.form.get('fecha_firma')),
            observaciones=request.form.get('observaciones', '').strip(),
        )
        db.session.add(registro)
        db.session.commit()
        registrar_log('CREACION', 'Capacitaciones',
                      f'Registro de entrenamiento de {registro.empleado_nombre}')
        flash('Registro de entrenamiento creado.', 'success')
        return redirect(url_for('capacitaciones.entrenamientos'))
    return render_template('capacitaciones/entrenamiento_form.html', **_contexto())


@capacitaciones_bp.route('/entrenamientos/disclosure/pdf')
@login_required
def disclosure_pdf():
    doc_id = request.args.get('documento_id', type=int)
    cargo = request.args.get('cargo', '').strip()
    if not doc_id:
        flash('Seleccione un documento para generar el disclosure.', 'warning')
        return redirect(url_for('capacitaciones.entrenamientos'))
    documento = db.get_or_404(Documento, doc_id)
    consulta = RegistroEntrenamiento.query.filter_by(documento_id=doc_id)
    if cargo:
        consulta = consulta.filter_by(cargo=cargo)
    registros = consulta.order_by(RegistroEntrenamiento.empleado_nombre).all()
    archivo = pdf_service.pdf_disclosure(documento, cargo, registros)
    return send_file(archivo, as_attachment=True,
                     download_name=f'disclosure_{documento.codigo}.pdf',
                     mimetype='application/pdf')


@capacitaciones_bp.route('/entrenamientos/exportar/excel')
@login_required
def exportar_entrenamientos():
    registros = RegistroEntrenamiento.query\
        .order_by(RegistroEntrenamiento.fecha_entrenamiento.desc()).all()
    filas = [[r.empleado_nombre, r.cargo,
              r.departamento.nombre if r.departamento else '',
              r.documento.codigo if r.documento else '',
              r.documento.titulo if r.documento else '',
              r.fecha_entrenamiento.strftime('%d/%m/%Y') if r.fecha_entrenamiento else '',
              r.entrenado_por or '',
              'Sí' if r.firmo_disclosure else 'No',
              r.fecha_firma.strftime('%d/%m/%Y') if r.fecha_firma else '']
             for r in registros]
    archivo = excel_service.exportar_excel(
        'Reporte de Entrenamiento', 'Entrenamientos',
        ['Empleado', 'Cargo', 'Departamento', 'Código Doc.', 'Documento',
         'F. Entrenamiento', 'Entrenado por', 'Firmó', 'F. Firma'],
        filas)
    registrar_log('EXPORTACION', 'Capacitaciones', 'Entrenamientos exportados a Excel')
    return send_file(archivo, as_attachment=True, download_name='entrenamientos.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
