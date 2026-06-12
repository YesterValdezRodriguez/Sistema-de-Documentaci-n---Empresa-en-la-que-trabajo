"""Modelos del módulo CAPA (Acciones Correctivas y Preventivas)."""
from datetime import datetime, date
from app.extensions import db

TIPOS_CAPA = ('CORRECTIVA', 'PREVENTIVA', 'MEJORA')
ORIGENES_CAPA = ('AUDITORIA', 'DESVIACION', 'RECLAMO', 'PROACTIVA', 'OTRO')
PRIORIDADES_CAPA = ('ALTA', 'MEDIA', 'BAJA')
ESTADOS_CAPA = ('ABIERTA', 'EN_PROCESO', 'VERIFICACION', 'CERRADA', 'VENCIDA')

ESTADOS_CAPA_NOMBRES = {
    'ABIERTA': 'Abierta',
    'EN_PROCESO': 'En Proceso',
    'VERIFICACION': 'Verificación',
    'CERRADA': 'Cerrada',
    'VENCIDA': 'Vencida',
}

ESTADOS_ACCION = ('PENDIENTE', 'EN_PROCESO', 'COMPLETADA')


class CAPA(db.Model):
    __tablename__ = 'capas'

    id = db.Column(db.Integer, primary_key=True)
    numero_capa = db.Column(db.String(20), unique=True, nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False)
    origen = db.Column(db.String(20), nullable=False)
    titulo = db.Column(db.String(255), nullable=False)
    descripcion_hallazgo = db.Column(db.Text)
    descripcion_problema = db.Column(db.Text)
    area_afectada = db.Column(db.String(120))
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'))
    responsable_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_apertura = db.Column(db.Date, default=datetime.utcnow)
    fecha_limite_implementacion = db.Column(db.Date, index=True)
    prioridad = db.Column(db.String(10), default='MEDIA', nullable=False)
    estado = db.Column(db.String(20), default='ABIERTA', nullable=False, index=True)

    # Análisis de causa raíz
    metodo_analisis = db.Column(db.String(120))
    causa_raiz_identificada = db.Column(db.Text)

    # Plan de acción
    acciones_correctivas = db.Column(db.Text)
    recursos_necesarios = db.Column(db.Text)

    # Implementación
    evidencia_implementacion = db.Column(db.Text)
    implementado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_implementacion = db.Column(db.Date)

    # Cierre
    verificado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_verificacion = db.Column(db.Date)
    efectividad_verificada = db.Column(db.Boolean, default=False)
    comentario_cierre = db.Column(db.Text)
    fecha_cierre = db.Column(db.Date)
    cerrado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    departamento = db.relationship('Departamento', backref='capas')
    responsable = db.relationship('Usuario', foreign_keys=[responsable_id])
    implementado_por = db.relationship('Usuario', foreign_keys=[implementado_por_id])
    verificado_por = db.relationship('Usuario', foreign_keys=[verificado_por_id])
    cerrado_por = db.relationship('Usuario', foreign_keys=[cerrado_por_id])
    creado_por = db.relationship('Usuario', foreign_keys=[creado_por_id])
    acciones = db.relationship('AccionCAPA', backref='capa', cascade='all, delete-orphan')

    @property
    def estado_nombre(self):
        return ESTADOS_CAPA_NOMBRES.get(self.estado, self.estado)

    @property
    def esta_vencida(self):
        return (self.estado not in ('CERRADA',) and self.fecha_limite_implementacion
                and self.fecha_limite_implementacion < date.today())

    def __repr__(self):
        return f'<CAPA {self.numero_capa}>'


class AccionCAPA(db.Model):
    __tablename__ = 'acciones_capa'

    id = db.Column(db.Integer, primary_key=True)
    capa_id = db.Column(db.Integer, db.ForeignKey('capas.id'), nullable=False)
    descripcion_accion = db.Column(db.Text, nullable=False)
    responsable_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_limite = db.Column(db.Date)
    estado = db.Column(db.String(20), default='PENDIENTE', nullable=False)
    fecha_completada = db.Column(db.Date)
    evidencia = db.Column(db.Text)

    responsable = db.relationship('Usuario')
