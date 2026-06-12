"""Módulo 5 — Auditorías y hallazgos."""
from datetime import date
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, send_file, current_app)
from flask_login import login_required, current_user
from app.extensions import db
from app.models.auditoria import (Auditoria, HallazgoAuditoria, TIPOS_AUDITORIA,
                                  ESTADOS_AUDITORIA, TIPOS_HALLAZGO)
from app.models.capa import CAPA
from app.models.user import Usuario
from app.utils.decorators import rol_requerido
from app.utils.helpers import parse_fecha, registrar_log, generar_numero
from app.services import pdf_service, excel_service

auditorias_bp = Blueprint('auditorias', __name__)


def _contexto():
    return {
        'tipos': TIPOS_AUDITORIA,
        'estados': ESTADOS_AUDITORIA,
        'tipos_hallazgo': TIPOS_HALLAZGO,
        'usuarios': Usuario.query.filter_by(activo=True)
                                 .order_by(Usuario.nombre_completo).all(),
    }


@auditorias_bp.route('/')
@login_required
def lista():
    pagina = request.args.get('pagina', 1, type=int)
    consulta = Auditoria.query
    estado = request.args.get('estado', '')
    tipo = request.args.get('tipo', '')
    if estado:
        consulta = consulta.filter_by(estado=estado)
    if tipo:
        consulta = consulta.filter_by(tipo=tipo)
    paginacion = consulta.order_by(Auditoria.numero_auditoria.desc()).paginate(
        page=pagina, per_page=current_app.config['REGISTROS_POR_PAGINA'], error_out=False)
    return render_template('auditorias/lista.html', paginacion=paginacion,
                           auditorias=paginacion.items, **_contexto())


@auditorias_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def nueva():
    if request.method == 'POST':
        aud = Auditoria(
            numero_auditoria=generar_numero(Auditoria, 'numero_auditoria', 'AUD'),
            tipo=request.form.get('tipo', 'INTERNA'),
            titulo=request.form.get('titulo', '').strip(),
            alcance=request.form.get('alcance', '').strip(),
            objetivo=request.form.get('objetivo', '').strip(),
            fecha_inicio=parse_fecha(request.form.get('fecha_inicio')),
            fecha_fin_planificada=parse_fecha(request.form.get('fecha_fin_planificada')),
            auditor_lider=request.form.get('auditor_lider', '').strip(),
            equipo_auditor=request.form.get('equipo_auditor', '').strip(),
            departamentos_auditados=request.form.get('departamentos_auditados', '').strip(),
            creado_por_id=current_user.id,
        )
        db.session.add(aud)
        db.session.commit()
        registrar_log('CREACION', 'Auditorías', f'{aud.numero_auditoria} planificada')
        flash(f'Auditoría {aud.numero_auditoria} planificada.', 'success')
        return redirect(url_for('auditorias.detalle', id=aud.id))
    return render_template('auditorias/form.html', auditoria=None, **_contexto())


@auditorias_bp.route('/<int:id>')
@login_required
def detalle(id):
    aud = db.get_or_404(Auditoria, id)
    return render_template('auditorias/detalle.html', auditoria=aud, **_contexto())


@auditorias_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def editar(id):
    aud = db.get_or_404(Auditoria, id)
    if request.method == 'POST':
        aud.tipo = request.form.get('tipo', aud.tipo)
        aud.titulo = request.form.get('titulo', '').strip()
        aud.alcance = request.form.get('alcance', '').strip()
        aud.objetivo = request.form.get('objetivo', '').strip()
        aud.fecha_inicio = parse_fecha(request.form.get('fecha_inicio'))
        aud.fecha_fin_planificada = parse_fecha(request.form.get('fecha_fin_planificada'))
        aud.auditor_lider = request.form.get('auditor_lider', '').strip()
        aud.equipo_auditor = request.form.get('equipo_auditor', '').strip()
        aud.departamentos_auditados = request.form.get('departamentos_auditados', '').strip()
        db.session.commit()
        registrar_log('EDICION', 'Auditorías', f'{aud.numero_auditoria} editada')
        flash('Auditoría actualizada.', 'success')
        return redirect(url_for('auditorias.detalle', id=aud.id))
    return render_template('auditorias/form.html', auditoria=aud, **_contexto())


@auditorias_bp.route('/<int:id>/cambiar-estado', methods=['POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def cambiar_estado(id):
    aud = db.get_or_404(Auditoria, id)
    nuevo_estado = request.form.get('estado')
    if nuevo_estado in ESTADOS_AUDITORIA:
        aud.estado = nuevo_estado
        if nuevo_estado == 'CERRADA':
            aud.fecha_informe = aud.fecha_informe or date.today()
            aud.resumen_ejecutivo = request.form.get(
                'resumen_ejecutivo', aud.resumen_ejecutivo or '').strip()
        db.session.commit()
        registrar_log('FLUJO', 'Auditorías', f'{aud.numero_auditoria} → {nuevo_estado}')
        flash(f'Auditoría actualizada a estado {aud.estado_nombre}.', 'success')
    return redirect(url_for('auditorias.detalle', id=id))


# ---------------------------------------------------------------- Hallazgos

@auditorias_bp.route('/<int:id>/hallazgos/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def nuevo_hallazgo(id):
    aud = db.get_or_404(Auditoria, id)
    if request.method == 'POST':
        hallazgo = HallazgoAuditoria(
            auditoria_id=aud.id,
            tipo_hallazgo=request.form.get('tipo_hallazgo', 'OBSERVACION'),
            descripcion=request.form.get('descripcion', '').strip(),
            requisito_incumplido=request.form.get('requisito_incumplido', '').strip(),
            evidencia_objetiva=request.form.get('evidencia_objetiva', '').strip(),
            responsable_respuesta_id=request.form.get(
                'responsable_respuesta_id', type=int) or None,
            fecha_limite_respuesta=parse_fecha(request.form.get('fecha_limite_respuesta')),
        )
        db.session.add(hallazgo)
        db.session.commit()
        registrar_log('CREACION', 'Auditorías',
                      f'Hallazgo registrado en {aud.numero_auditoria}')
        flash('Hallazgo registrado.', 'success')
        return redirect(url_for('auditorias.detalle', id=aud.id))
    return render_template('auditorias/hallazgo_form.html', auditoria=aud, **_contexto())


@auditorias_bp.route('/hallazgos/<int:id>/responder', methods=['POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def responder_hallazgo(id):
    hallazgo = db.get_or_404(HallazgoAuditoria, id)
    hallazgo.respuesta = request.form.get('respuesta', '').strip()
    hallazgo.fecha_respuesta = date.today()
    hallazgo.estado = 'EN_PROCESO'
    db.session.commit()
    registrar_log('EDICION', 'Auditorías', f'Respuesta a hallazgo #{hallazgo.id}')
    flash('Respuesta registrada.', 'success')
    return redirect(url_for('auditorias.detalle', id=hallazgo.auditoria_id))


@auditorias_bp.route('/hallazgos/<int:id>/cerrar', methods=['POST'])
@login_required
@rol_requerido('aprobador')
def cerrar_hallazgo(id):
    hallazgo = db.get_or_404(HallazgoAuditoria, id)
    hallazgo.estado = 'CERRADO'
    db.session.commit()
    registrar_log('CIERRE', 'Auditorías', f'Hallazgo #{hallazgo.id} cerrado')
    flash('Hallazgo cerrado.', 'success')
    return redirect(url_for('auditorias.detalle', id=hallazgo.auditoria_id))


@auditorias_bp.route('/hallazgos/<int:id>/generar-capa', methods=['POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def generar_capa(id):
    hallazgo = db.get_or_404(HallazgoAuditoria, id)
    if hallazgo.capa_generada_id:
        flash('Este hallazgo ya tiene una CAPA vinculada.', 'warning')
        return redirect(url_for('auditorias.detalle', id=hallazgo.auditoria_id))

    capa = CAPA(
        numero_capa=generar_numero(CAPA, 'numero_capa', 'CAPA'),
        tipo='CORRECTIVA',
        origen='AUDITORIA',
        titulo=f'Hallazgo de {hallazgo.auditoria.numero_auditoria}: '
               f'{hallazgo.tipo_nombre}',
        descripcion_hallazgo=hallazgo.descripcion,
        descripcion_problema=hallazgo.requisito_incumplido,
        area_afectada=hallazgo.auditoria.departamentos_auditados,
        responsable_id=hallazgo.responsable_respuesta_id,
        fecha_apertura=date.today(),
        fecha_limite_implementacion=hallazgo.fecha_limite_respuesta,
        prioridad='ALTA' if hallazgo.tipo_hallazgo == 'NO_CONFORMIDAD_MAYOR' else 'MEDIA',
        creado_por_id=current_user.id,
    )
    db.session.add(capa)
    db.session.flush()
    hallazgo.capa_generada_id = capa.id
    db.session.commit()
    registrar_log('CREACION', 'Auditorías',
                  f'CAPA {capa.numero_capa} generada desde hallazgo #{hallazgo.id}')
    flash(f'CAPA {capa.numero_capa} generada y vinculada al hallazgo.', 'success')
    return redirect(url_for('capas.detalle', id=capa.id))


# ----------------------------------------------------------------- Reportes

@auditorias_bp.route('/<int:id>/pdf')
@login_required
def informe_pdf(id):
    aud = db.get_or_404(Auditoria, id)
    archivo = pdf_service.pdf_auditoria(aud)
    return send_file(archivo, as_attachment=True,
                     download_name=f'informe_{aud.numero_auditoria}.pdf',
                     mimetype='application/pdf')


@auditorias_bp.route('/exportar/hallazgos/excel')
@login_required
def exportar_hallazgos():
    hallazgos = HallazgoAuditoria.query.join(Auditoria)\
        .order_by(Auditoria.numero_auditoria.desc()).all()
    filas = [[h.auditoria.numero_auditoria, h.tipo_nombre, h.descripcion,
              h.requisito_incumplido or '', h.evidencia_objetiva or '',
              h.capa_generada.numero_capa if h.capa_generada else '',
              h.responsable_respuesta.nombre_completo if h.responsable_respuesta else '',
              h.fecha_limite_respuesta.strftime('%d/%m/%Y')
              if h.fecha_limite_respuesta else '',
              h.estado]
             for h in hallazgos]
    archivo = excel_service.exportar_excel(
        'Hallazgos de Auditoría', 'Hallazgos',
        ['Auditoría', 'Tipo', 'Descripción', 'Requisito', 'Evidencia', 'CAPA',
         'Responsable', 'F. Límite', 'Estado'],
        filas)
    registrar_log('EXPORTACION', 'Auditorías', 'Hallazgos exportados a Excel')
    return send_file(archivo, as_attachment=True, download_name='hallazgos_auditoria.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
