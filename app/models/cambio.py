"""Modelos del módulo de Control de Cambios."""
from datetime import datetime
from app.extensions import db

ESTADOS_SC = ('ABIERTA', 'EN_EVALUACION', 'APROBADA', 'RECHAZADA', 'IMPLEMENTADA', 'CERRADA')

ESTADOS_SC_NOMBRES = {
    'ABIERTA': 'Abierta',
    'EN_EVALUACION': 'En Evaluación',
    'APROBADA': 'Aprobada',
    'RECHAZADA': 'Rechazada',
    'IMPLEMENTADA': 'Implementada',
    'CERRADA': 'Cerrada',
}

TIPOS_CAMBIO = (
    'Cambio de documento',
    'Cambio de proceso',
    'Cambio de equipamiento',
    'Cambio de proveedor',
    'Cambio de materias primas',
    'Otro',
)


class SolicitudCambio(db.Model):
    __tablename__ = 'solicitudes_cambio'

    id = db.Column(db.Integer, primary_key=True)
    numero_sc = db.Column(db.String(20), unique=True, nullable=False, index=True)
    titulo = db.Column(db.String(255), nullable=False)
    tipo_cambio = db.Column(db.String(60), nullable=False)
    descripcion_cambio = db.Column(db.Text, nullable=False)
    justificacion = db.Column(db.Text)
    impacto_estimado = db.Column(db.Text)
    documento_afectado_id = db.Column(db.Integer, db.ForeignKey('documentos.id'))
    area_afectada = db.Column(db.String(120))
    solicitado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_solicitud = db.Column(db.Date, default=datetime.utcnow)
    estado = db.Column(db.String(20), default='ABIERTA', nullable=False, index=True)
    evaluado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_evaluacion = db.Column(db.Date)
    decision = db.Column(db.String(20))
    comentario_evaluacion = db.Column(db.Text)
    implementado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_implementacion = db.Column(db.Date)
    evidencia_implementacion = db.Column(db.Text)
    cerrado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_cierre = db.Column(db.Date)

    documento_afectado = db.relationship('Documento', backref='solicitudes_cambio')
    solicitado_por = db.relationship('Usuario', foreign_keys=[solicitado_por_id])
    evaluado_por = db.relationship('Usuario', foreign_keys=[evaluado_por_id])
    implementado_por = db.relationship('Usuario', foreign_keys=[implementado_por_id])
    cerrado_por = db.relationship('Usuario', foreign_keys=[cerrado_por_id])
    comentarios = db.relationship('ComentarioCambio', backref='solicitud',
                                  order_by='ComentarioCambio.fecha_hora.desc()',
                                  cascade='all, delete-orphan')

    @property
    def estado_nombre(self):
        return ESTADOS_SC_NOMBRES.get(self.estado, self.estado)

    def __repr__(self):
        return f'<SolicitudCambio {self.numero_sc}>'


class ComentarioCambio(db.Model):
    __tablename__ = 'comentarios_cambio'

    id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitudes_cambio.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    comentario = db.Column(db.Text, nullable=False)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario')
