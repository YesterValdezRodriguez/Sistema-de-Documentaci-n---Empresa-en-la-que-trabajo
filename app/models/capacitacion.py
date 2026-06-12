"""Modelos del módulo de Capacitación y Entrenamiento."""
from datetime import datetime
from app.extensions import db

TIPOS_PLAN = ('induccion', 'reentrenamiento', 'anual', 'puntual')

TIPOS_PLAN_NOMBRES = {
    'induccion': 'Inducción',
    'reentrenamiento': 'Reentrenamiento',
    'anual': 'Anual',
    'puntual': 'Puntual',
}

ESTADOS_SESION = ('PROGRAMADA', 'REALIZADA', 'CANCELADA')

ESTADOS_SESION_NOMBRES = {
    'PROGRAMADA': 'Programada',
    'REALIZADA': 'Realizada',
    'CANCELADA': 'Cancelada',
}


class PlanCapacitacion(db.Model):
    __tablename__ = 'planes_capacitacion'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    descripcion = db.Column(db.Text)
    tipo = db.Column(db.String(20), nullable=False, default='puntual')
    documento_id = db.Column(db.Integer, db.ForeignKey('documentos.id'))
    cargo_aplica = db.Column(db.String(255))
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'))
    frecuencia_meses = db.Column(db.Integer, default=0)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    documento = db.relationship('Documento', backref='planes_capacitacion')
    departamento = db.relationship('Departamento', backref='planes_capacitacion')
    sesiones = db.relationship('SesionCapacitacion', backref='plan',
                               order_by='SesionCapacitacion.fecha_sesion.desc()',
                               cascade='all, delete-orphan')

    @property
    def tipo_nombre(self):
        return TIPOS_PLAN_NOMBRES.get(self.tipo, self.tipo)

    def __repr__(self):
        return f'<PlanCapacitacion {self.titulo}>'


class SesionCapacitacion(db.Model):
    __tablename__ = 'sesiones_capacitacion'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('planes_capacitacion.id'))
    titulo = db.Column(db.String(255), nullable=False)
    fecha_sesion = db.Column(db.Date, nullable=False, index=True)
    hora_inicio = db.Column(db.String(5))
    hora_fin = db.Column(db.String(5))
    facilitador = db.Column(db.String(120))
    lugar = db.Column(db.String(120))
    objetivo = db.Column(db.Text)
    contenido_impartido = db.Column(db.Text)
    estado = db.Column(db.String(20), default='PROGRAMADA', nullable=False)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    creado_por = db.relationship('Usuario')
    asistencias = db.relationship('AsistenciaCapacitacion', backref='sesion',
                                  cascade='all, delete-orphan')

    @property
    def estado_nombre(self):
        return ESTADOS_SESION_NOMBRES.get(self.estado, self.estado)

    def __repr__(self):
        return f'<SesionCapacitacion {self.titulo} {self.fecha_sesion}>'


class AsistenciaCapacitacion(db.Model):
    __tablename__ = 'asistencias_capacitacion'

    id = db.Column(db.Integer, primary_key=True)
    sesion_id = db.Column(db.Integer, db.ForeignKey('sesiones_capacitacion.id'), nullable=False)
    participante_nombre = db.Column(db.String(120), nullable=False)
    participante_cargo = db.Column(db.String(120))
    participante_departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'))
    firmo = db.Column(db.Boolean, default=False)
    calificacion = db.Column(db.Integer)
    aprobado = db.Column(db.Boolean, default=False)
    observaciones = db.Column(db.Text)

    participante_departamento = db.relationship('Departamento')


class RegistroEntrenamiento(db.Model):
    """Registro de entrenamiento / disclosure por posición y documento."""
    __tablename__ = 'registros_entrenamiento'

    id = db.Column(db.Integer, primary_key=True)
    cargo = db.Column(db.String(120), nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'))
    documento_id = db.Column(db.Integer, db.ForeignKey('documentos.id'), nullable=False)
    empleado_nombre = db.Column(db.String(120), nullable=False)
    fecha_entrenamiento = db.Column(db.Date)
    entrenado_por = db.Column(db.String(120))
    firmo_disclosure = db.Column(db.Boolean, default=False)
    fecha_firma = db.Column(db.Date)
    observaciones = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    departamento = db.relationship('Departamento')
    documento = db.relationship('Documento', backref='registros_entrenamiento')
