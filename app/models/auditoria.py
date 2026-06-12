"""Modelos del módulo de Auditorías."""
from datetime import datetime
from app.extensions import db

TIPOS_AUDITORIA = ('INTERNA', 'EXTERNA', 'REGULATORIA', 'PROVEEDOR')
ESTADOS_AUDITORIA = ('PLANIFICADA', 'EN_CURSO', 'INFORME_PENDIENTE', 'CERRADA')

ESTADOS_AUDITORIA_NOMBRES = {
    'PLANIFICADA': 'Planificada',
    'EN_CURSO': 'En Curso',
    'INFORME_PENDIENTE': 'Informe Pendiente',
    'CERRADA': 'Cerrada',
}

TIPOS_HALLAZGO = ('NO_CONFORMIDAD_MAYOR', 'NO_CONFORMIDAD_MENOR', 'OBSERVACION', 'OPORTUNIDAD_MEJORA')

TIPOS_HALLAZGO_NOMBRES = {
    'NO_CONFORMIDAD_MAYOR': 'No Conformidad Mayor',
    'NO_CONFORMIDAD_MENOR': 'No Conformidad Menor',
    'OBSERVACION': 'Observación',
    'OPORTUNIDAD_MEJORA': 'Oportunidad de Mejora',
}

ESTADOS_HALLAZGO = ('ABIERTO', 'EN_PROCESO', 'CERRADO')


class Auditoria(db.Model):
    __tablename__ = 'auditorias'

    id = db.Column(db.Integer, primary_key=True)
    numero_auditoria = db.Column(db.String(20), unique=True, nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False)
    titulo = db.Column(db.String(255), nullable=False)
    alcance = db.Column(db.Text)
    objetivo = db.Column(db.Text)
    fecha_inicio = db.Column(db.Date)
    fecha_fin_planificada = db.Column(db.Date)
    auditor_lider = db.Column(db.String(120))
    equipo_auditor = db.Column(db.Text)
    departamentos_auditados = db.Column(db.Text)
    estado = db.Column(db.String(20), default='PLANIFICADA', nullable=False, index=True)
    fecha_informe = db.Column(db.Date)
    resumen_ejecutivo = db.Column(db.Text)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    creado_por = db.relationship('Usuario')
    hallazgos = db.relationship('HallazgoAuditoria', backref='auditoria',
                                cascade='all, delete-orphan')

    @property
    def estado_nombre(self):
        return ESTADOS_AUDITORIA_NOMBRES.get(self.estado, self.estado)

    def __repr__(self):
        return f'<Auditoria {self.numero_auditoria}>'


class HallazgoAuditoria(db.Model):
    __tablename__ = 'hallazgos_auditoria'

    id = db.Column(db.Integer, primary_key=True)
    auditoria_id = db.Column(db.Integer, db.ForeignKey('auditorias.id'), nullable=False)
    tipo_hallazgo = db.Column(db.String(30), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    requisito_incumplido = db.Column(db.Text)
    evidencia_objetiva = db.Column(db.Text)
    capa_generada_id = db.Column(db.Integer, db.ForeignKey('capas.id'))
    responsable_respuesta_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_limite_respuesta = db.Column(db.Date)
    respuesta = db.Column(db.Text)
    fecha_respuesta = db.Column(db.Date)
    estado = db.Column(db.String(20), default='ABIERTO', nullable=False)

    capa_generada = db.relationship('CAPA', backref='hallazgo_origen')
    responsable_respuesta = db.relationship('Usuario')

    @property
    def tipo_nombre(self):
        return TIPOS_HALLAZGO_NOMBRES.get(self.tipo_hallazgo, self.tipo_hallazgo)
