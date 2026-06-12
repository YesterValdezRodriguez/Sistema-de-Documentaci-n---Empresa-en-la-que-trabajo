"""Módulo 7 — Administración del sistema (solo admin)."""
import os
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, send_file, current_app)
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import Usuario, ROLES, ROLES_NOMBRES
from app.models.config_app import (Departamento, TipoDocumento, CargoPosicion,
                                   LogSistema, RegistroBackup)
from app.utils.decorators import rol_requerido
from app.utils.helpers import registrar_log, parse_fecha

administracion_bp = Blueprint('administracion', __name__)


# ----------------------------------------------------------------- Usuarios

@administracion_bp.route('/usuarios')
@login_required
@rol_requerido('admin')
def usuarios():
    lista_usuarios = Usuario.query.order_by(Usuario.username).all()
    return render_template('administracion/usuarios.html', usuarios=lista_usuarios,
                           roles=ROLES, roles_nombres=ROLES_NOMBRES)


def _datos_usuario_desde_form(usuario):
    usuario.username = request.form.get('username', '').strip()
    usuario.email = request.form.get('email', '').strip() or None
    usuario.nombre_completo = request.form.get('nombre_completo', '').strip()
    usuario.cargo = request.form.get('cargo', '').strip()
    usuario.departamento_id = request.form.get('departamento_id', type=int) or None
    usuario.rol = request.form.get('rol', 'usuario_lectura')


@administracion_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def nuevo_usuario():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if Usuario.query.filter_by(username=username).first():
            flash(f'El usuario "{username}" ya existe.', 'danger')
        else:
            usuario = Usuario()
            _datos_usuario_desde_form(usuario)
            usuario.set_password(request.form.get('password', 'cambiar123'))
            db.session.add(usuario)
            db.session.commit()
            registrar_log('CREACION', 'Administración', f'Usuario {username} creado')
            flash(f'Usuario {username} creado.', 'success')
            return redirect(url_for('administracion.usuarios'))
    departamentos = Departamento.query.filter_by(activo=True)\
        .order_by(Departamento.codigo).all()
    return render_template('administracion/usuario_form.html', usuario=None,
                           roles=ROLES, roles_nombres=ROLES_NOMBRES,
                           departamentos=departamentos)


@administracion_bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@rol_requerido('admin')
def editar_usuario(id):
    usuario = db.get_or_404(Usuario, id)
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        existente = Usuario.query.filter(Usuario.username == username,
                                         Usuario.id != usuario.id).first()
        if existente:
            flash(f'El usuario "{username}" ya existe.', 'danger')
        else:
            _datos_usuario_desde_form(usuario)
            db.session.commit()
            registrar_log('EDICION', 'Administración', f'Usuario {username} editado')
            flash('Usuario actualizado.', 'success')
            return redirect(url_for('administracion.usuarios'))
    departamentos = Departamento.query.filter_by(activo=True)\
        .order_by(Departamento.codigo).all()
    return render_template('administracion/usuario_form.html', usuario=usuario,
                           roles=ROLES, roles_nombres=ROLES_NOMBRES,
                           departamentos=departamentos)


@administracion_bp.route('/usuarios/<int:id>/toggle-activo', methods=['POST'])
@login_required
@rol_requerido('admin')
def toggle_activo_usuario(id):
    usuario = db.get_or_404(Usuario, id)
    if usuario.id == current_user.id:
        flash('No puede desactivar su propio usuario.', 'warning')
    else:
        usuario.activo = not usuario.activo
        db.session.commit()
        accion = 'activado' if usuario.activo else 'desactivado'
        registrar_log('EDICION', 'Administración', f'Usuario {usuario.username} {accion}')
        flash(f'Usuario {usuario.username} {accion}.', 'success')
    return redirect(url_for('administracion.usuarios'))


@administracion_bp.route('/usuarios/<int:id>/resetear-password', methods=['POST'])
@login_required
@rol_requerido('admin')
def resetear_password(id):
    usuario = db.get_or_404(Usuario, id)
    nueva = request.form.get('password_nueva', '').strip()
    if len(nueva) < 6:
        flash('La contraseña temporal debe tener al menos 6 caracteres.', 'warning')
    else:
        usuario.set_password(nueva)
        db.session.commit()
        registrar_log('EDICION', 'Administración',
                      f'Contraseña de {usuario.username} reseteada')
        flash(f'Contraseña de {usuario.username} reseteada.', 'success')
    return redirect(url_for('administracion.usuarios'))


# ---------------------------------------------------------------- Catálogos

@administracion_bp.route('/catalogos')
@login_required
@rol_requerido('admin')
def catalogos():
    return render_template(
        'administracion/catalogos.html',
        departamentos=Departamento.query.order_by(Departamento.codigo).all(),
        tipos=TipoDocumento.query.order_by(TipoDocumento.prefijo).all(),
        cargos=CargoPosicion.query.order_by(CargoPosicion.nombre).all(),
    )


@administracion_bp.route('/catalogos/departamentos/guardar', methods=['POST'])
@login_required
@rol_requerido('admin')
def guardar_departamento():
    depto_id = request.form.get('id', type=int)
    depto = db.session.get(Departamento, depto_id) if depto_id else Departamento()
    depto.codigo = request.form.get('codigo', '').strip().upper()
    depto.nombre = request.form.get('nombre', '').strip()
    depto.jefe = request.form.get('jefe', '').strip()
    depto.activo = bool(request.form.get('activo'))
    if not depto_id:
        db.session.add(depto)
    db.session.commit()
    registrar_log('EDICION' if depto_id else 'CREACION', 'Administración',
                  f'Departamento {depto.codigo}')
    flash('Departamento guardado.', 'success')
    return redirect(url_for('administracion.catalogos'))


@administracion_bp.route('/catalogos/tipos/guardar', methods=['POST'])
@login_required
@rol_requerido('admin')
def guardar_tipo():
    tipo_id = request.form.get('id', type=int)
    tipo = db.session.get(TipoDocumento, tipo_id) if tipo_id else TipoDocumento()
    tipo.prefijo = request.form.get('prefijo', '').strip().upper()
    tipo.nombre = request.form.get('nombre', '').strip()
    tipo.descripcion = request.form.get('descripcion', '').strip()
    tipo.activo = bool(request.form.get('activo'))
    if not tipo_id:
        db.session.add(tipo)
    db.session.commit()
    registrar_log('EDICION' if tipo_id else 'CREACION', 'Administración',
                  f'Tipo de documento {tipo.prefijo}')
    flash('Tipo de documento guardado.', 'success')
    return redirect(url_for('administracion.catalogos'))


@administracion_bp.route('/catalogos/cargos/guardar', methods=['POST'])
@login_required
@rol_requerido('admin')
def guardar_cargo():
    cargo_id = request.form.get('id', type=int)
    cargo = db.session.get(CargoPosicion, cargo_id) if cargo_id else CargoPosicion()
    cargo.nombre = request.form.get('nombre', '').strip()
    cargo.departamento_id = request.form.get('departamento_id', type=int) or None
    cargo.descripcion = request.form.get('descripcion', '').strip()
    cargo.activo = bool(request.form.get('activo'))
    if not cargo_id:
        db.session.add(cargo)
    db.session.commit()
    registrar_log('EDICION' if cargo_id else 'CREACION', 'Administración',
                  f'Cargo {cargo.nombre}')
    flash('Cargo guardado.', 'success')
    return redirect(url_for('administracion.catalogos'))


# -------------------------------------------------------------- Log sistema

@administracion_bp.route('/log')
@login_required
@rol_requerido('admin')
def log():
    pagina = request.args.get('pagina', 1, type=int)
    consulta = LogSistema.query
    usuario_id = request.args.get('usuario', type=int)
    modulo = request.args.get('modulo', '').strip()
    fecha_desde = parse_fecha(request.args.get('desde'))
    fecha_hasta = parse_fecha(request.args.get('hasta'))
    if usuario_id:
        consulta = consulta.filter_by(usuario_id=usuario_id)
    if modulo:
        consulta = consulta.filter(LogSistema.modulo.ilike(f'%{modulo}%'))
    if fecha_desde:
        consulta = consulta.filter(db.func.date(LogSistema.fecha_hora) >= fecha_desde)
    if fecha_hasta:
        consulta = consulta.filter(db.func.date(LogSistema.fecha_hora) <= fecha_hasta)
    paginacion = consulta.order_by(LogSistema.fecha_hora.desc()).paginate(
        page=pagina, per_page=current_app.config['REGISTROS_POR_PAGINA'], error_out=False)
    lista_usuarios = Usuario.query.order_by(Usuario.username).all()
    return render_template('administracion/log.html', paginacion=paginacion,
                           registros=paginacion.items, usuarios=lista_usuarios)


# ------------------------------------------------------------------- Backup

@administracion_bp.route('/backup')
@login_required
@rol_requerido('admin')
def backup():
    registros = RegistroBackup.query.order_by(RegistroBackup.fecha_hora.desc())\
        .limit(50).all()
    return render_template('administracion/backup.html', registros=registros)


@administracion_bp.route('/backup/descargar', methods=['POST'])
@login_required
@rol_requerido('admin')
def descargar_backup():
    uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    ruta_db = uri.replace('sqlite:///', '')
    if not os.path.exists(ruta_db):
        flash('No se encontró el archivo de base de datos.', 'danger')
        return redirect(url_for('administracion.backup'))

    nombre = f'qms_farach_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    db.session.add(RegistroBackup(
        usuario_id=current_user.id,
        nombre_archivo=nombre,
        tamano_bytes=os.path.getsize(ruta_db),
    ))
    db.session.commit()
    registrar_log('BACKUP', 'Administración', f'Backup descargado: {nombre}')
    return send_file(ruta_db, as_attachment=True, download_name=nombre,
                     mimetype='application/octet-stream')
