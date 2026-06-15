"""QMS FARACH - Fábrica de la aplicación Flask."""
import os
from flask import Flask, render_template, session
from config import config_por_nombre
from app.extensions import db, login_manager, migrate, csrf


def create_app(config_name=None):
    config_name = config_name or os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__)
    app.config.from_object(config_por_nombre[config_name])

    # Extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Debe iniciar sesión para acceder a esta página.'
    login_manager.login_message_category = 'warning'

    # Modelos (necesarios para create_all y migraciones)
    from app.models import user, config_app, documento, cambio, capacitacion, capa, auditoria  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(user.Usuario, int(user_id))

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.documentos import documentos_bp
    from app.routes.cambios import cambios_bp
    from app.routes.capacitaciones import capacitaciones_bp
    from app.routes.capas import capas_bp
    from app.routes.auditorias import auditorias_bp
    from app.routes.administracion import administracion_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(documentos_bp, url_prefix='/documentos')
    app.register_blueprint(cambios_bp, url_prefix='/cambios')
    app.register_blueprint(capacitaciones_bp, url_prefix='/capacitaciones')
    app.register_blueprint(capas_bp, url_prefix='/capas')
    app.register_blueprint(auditorias_bp, url_prefix='/auditorias')
    app.register_blueprint(administracion_bp, url_prefix='/administracion')

    # Filtros Jinja
    from app.utils.helpers import formato_fecha, formato_fecha_hora, badge_estado
    app.jinja_env.filters['fecha'] = formato_fecha
    app.jinja_env.filters['fecha_hora'] = formato_fecha_hora
    app.jinja_env.filters['badge_estado'] = badge_estado
    # Quita el parámetro de página al construir enlaces de paginación
    app.jinja_env.filters['reject_pagina'] = (
        lambda d: {k: v for k, v in d.items() if k != 'pagina'})

    # Sesión permanente (timeout de 8 horas definido en config)
    @app.before_request
    def hacer_sesion_permanente():
        session.permanent = True

    # Páginas de error personalizadas
    @app.errorhandler(403)
    def error_403(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def error_404(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def error_500(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # Crear tablas y cargar datos iniciales en el primer arranque
    with app.app_context():
        db.create_all()
        from app.utils.seed import seed_inicial
        seed_inicial()

    return app
