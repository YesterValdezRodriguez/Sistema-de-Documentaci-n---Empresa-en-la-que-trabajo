"""Modelo de Usuario y roles del sistema."""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

ROLES = ('admin', 'gestor_doc', 'aprobador', 'usuario_lectura')

ROLES_NOMBRES = {
    'admin': 'Administrador',
    'gestor_doc': 'Gestor Documental',
    'aprobador': 'Aprobador',
    'usuario_lectura': 'Usuario de Lectura',
}


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre_completo = db.Column(db.String(120), nullable=False)
    cargo = db.Column(db.String(120))
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'))
    rol = db.Column(db.String(20), nullable=False, default='usuario_lectura')
    activo = db.Column(db.Boolean, default=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acceso = db.Column(db.DateTime)

    departamento = db.relationship('Departamento', backref='usuarios')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def rol_nombre(self):
        return ROLES_NOMBRES.get(self.rol, self.rol)

    def tiene_rol(self, *roles):
        return self.rol in roles

    def __repr__(self):
        return f'<Usuario {self.username}>'
