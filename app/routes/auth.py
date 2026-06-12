"""Módulo 0 — Autenticación: login, logout y cambio de contraseña."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import Usuario
from app.utils.helpers import registrar_log

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        usuario = Usuario.query.filter_by(username=username).first()

        if usuario and usuario.activo and usuario.check_password(password):
            login_user(usuario)
            usuario.ultimo_acceso = datetime.utcnow()
            db.session.commit()
            registrar_log('LOGIN', 'Autenticación', f'Inicio de sesión de {username}')
            destino = request.args.get('next')
            if destino and destino.startswith('/'):
                return redirect(destino)
            return redirect(url_for('dashboard.index'))

        flash('Usuario o contraseña incorrectos, o usuario inactivo.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    registrar_log('LOGOUT', 'Autenticación', f'Cierre de sesión de {current_user.username}')
    logout_user()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/cambiar-password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    if request.method == 'POST':
        actual = request.form.get('password_actual', '')
        nueva = request.form.get('password_nueva', '')
        confirmacion = request.form.get('password_confirmacion', '')

        if not current_user.check_password(actual):
            flash('La contraseña actual es incorrecta.', 'danger')
        elif len(nueva) < 6:
            flash('La nueva contraseña debe tener al menos 6 caracteres.', 'warning')
        elif nueva != confirmacion:
            flash('La confirmación no coincide con la nueva contraseña.', 'warning')
        else:
            current_user.set_password(nueva)
            db.session.commit()
            registrar_log('CAMBIO_PASSWORD', 'Autenticación', 'Cambio de contraseña propio')
            flash('Contraseña actualizada correctamente.', 'success')
            return redirect(url_for('dashboard.index'))

    return render_template('auth/cambiar_password.html')
