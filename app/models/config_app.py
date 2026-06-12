"""Catálogos del sistema: departamentos, tipos de documento, cargos, log y backups."""
from datetime import datetime
from app.extensions import db


class Departamento(db.Model):
    __tablename__ = 'departamentos'

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    jefe = db.Column(db.String(120))
    activo = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<Departamento {self.codigo}>'


class TipoDocumento(db.Model):
    __tablename__ = 'tipos_documento'

    id = db.Column(db.Integer, primary_key=True)
    prefijo = db.Column(db.String(10), unique=True, nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    descripcion = db.Column(db.Text)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<TipoDocumento {self.prefijo}>'


class CargoPosicion(db.Model):
    __tablename__ = 'cargos_posiciones'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), unique=True, nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'))
    descripcion = db.Column(db.Text)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    departamento = db.relationship('Departamento', backref='cargos')

    def __repr__(self):
        return f'<CargoPosicion {self.nombre}>'


class LogSistema(db.Model):
    __tablename__ = 'log_sistema'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    accion = db.Column(db.String(50), nullable=False)
    modulo = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45))

    usuario = db.relationship('Usuario', backref='logs')

    def __repr__(self):
        return f'<LogSistema {self.accion} {self.modulo}>'


class RegistroBackup(db.Model):
    __tablename__ = 'registros_backup'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    nombre_archivo = db.Column(db.String(255), nullable=False)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)
    tamano_bytes = db.Column(db.Integer)

    usuario = db.relationship('Usuario', backref='backups')
