"""Modelos del módulo de Gestión de Documentos (sistema FAFII)."""
from datetime import datetime
from app.extensions import db

ESTADOS_DOCUMENTO = ('BORRADOR', 'EN_REVISION', 'APROBADO', 'VIGENTE', 'OBSOLETO')

ESTADOS_DOCUMENTO_NOMBRES = {
    'BORRADOR': 'Borrador',
    'EN_REVISION': 'En Revisión',
    'APROBADO': 'Aprobado',
    'VIGENTE': 'Vigente',
    'OBSOLETO': 'Obsoleto',
}


class Documento(db.Model):
    __tablename__ = 'documentos'

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False, index=True)
    titulo = db.Column(db.String(255), nullable=False)
    tipo_doc_id = db.Column(db.Integer, db.ForeignKey('tipos_documento.id'), nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'), nullable=False)
    version_actual = db.Column(db.String(10), default='01')
    estado = db.Column(db.String(20), default='BORRADOR', nullable=False, index=True)
    fecha_emision = db.Column(db.Date)
    fecha_vigencia = db.Column(db.Date)
    fecha_proxima_revision = db.Column(db.Date, index=True)
    elaborado_por = db.Column(db.String(120))
    revisado_por = db.Column(db.String(120))
    aprobado_por = db.Column(db.String(120))
    descripcion = db.Column(db.Text)
    alcance = db.Column(db.Text)
    aplica_a = db.Column(db.Text)
    ubicacion_fisica = db.Column(db.String(255))
    numero_copias_controladas = db.Column(db.Integer, default=0)
    motivo_baja = db.Column(db.Text)
    fecha_baja = db.Column(db.Date)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    tipo_doc = db.relationship('TipoDocumento', backref='documentos')
    departamento = db.relationship('Departamento', backref='documentos')
    creado_por = db.relationship('Usuario', backref='documentos_creados')
    versiones = db.relationship('VersionDocumento', backref='documento',
                                order_by='VersionDocumento.id.desc()',
                                cascade='all, delete-orphan')
    copias = db.relationship('DistribucionCopia', backref='documento',
                             cascade='all, delete-orphan')

    @property
    def estado_nombre(self):
        return ESTADOS_DOCUMENTO_NOMBRES.get(self.estado, self.estado)

    def __repr__(self):
        return f'<Documento {self.codigo}>'


class VersionDocumento(db.Model):
    __tablename__ = 'versiones_documento'

    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('documentos.id'), nullable=False)
    numero_version = db.Column(db.String(10), nullable=False)
    fecha_emision = db.Column(db.Date)
    cambios_realizados = db.Column(db.Text)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    aprobado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_aprobacion = db.Column(db.Date)
    archivo_nombre = db.Column(db.String(255))

    creado_por = db.relationship('Usuario', foreign_keys=[creado_por_id])
    aprobado_por = db.relationship('Usuario', foreign_keys=[aprobado_por_id])

    def __repr__(self):
        return f'<VersionDocumento {self.documento_id} v{self.numero_version}>'


class DistribucionCopia(db.Model):
    __tablename__ = 'distribucion_copias'

    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('documentos.id'), nullable=False)
    numero_copia = db.Column(db.Integer, nullable=False)
    destinatario = db.Column(db.String(120), nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'))
    fecha_entrega = db.Column(db.Date)
    entregado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    firmado = db.Column(db.Boolean, default=False)
    fecha_firma = db.Column(db.Date)
    observaciones = db.Column(db.Text)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    departamento = db.relationship('Departamento')
    entregado_por = db.relationship('Usuario')

    def __repr__(self):
        return f'<DistribucionCopia doc={self.documento_id} copia={self.numero_copia}>'
