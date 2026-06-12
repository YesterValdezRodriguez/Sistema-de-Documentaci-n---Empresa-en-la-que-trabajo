"""Datos iniciales del sistema (seeders)."""
from app.extensions import db
from app.models.user import Usuario
from app.models.config_app import Departamento, TipoDocumento, CargoPosicion

DEPARTAMENTOS_INICIALES = [
    ('GQ', 'Garantía de Calidad'),
    ('AC', 'Aseguramiento de Calidad / Control de Calidad'),
    ('PRD', 'Producción'),
    ('MANT', 'Mantenimiento'),
    ('ALM', 'Almacén'),
    ('RH', 'Recursos Humanos'),
    ('MKT', 'Marketing/Ventas'),
    ('LOG', 'Logística'),
    ('ADM', 'Administración'),
]

TIPOS_DOCUMENTO_INICIALES = [
    ('POE', 'Procedimiento Operativo Estándar', 'Procedimientos operativos estándar del sistema FAFII'),
    ('FOR', 'Formulario / Registro', 'Formularios y registros controlados'),
    ('INS', 'Instructivo de Trabajo', 'Instructivos de trabajo (INS/IT)'),
    ('IT', 'Instructivo de Trabajo (IT)', 'Instructivos de trabajo abreviados'),
    ('LG', 'Lista / Log', 'Listas y logs controlados'),
    ('POI', 'Política', 'Políticas institucionales'),
    ('PRO', 'Protocolo', 'Protocolos de validación y estudios'),
    ('REG', 'Registro', 'Registros del sistema de calidad'),
]

CARGOS_INICIALES = [
    'Gerente de Garantía de Calidad',
    'Analista de Control de Calidad',
    'Supervisor de Producción',
    'Operario de Producción',
    'Técnico de Mantenimiento',
    'Almacenista',
]


def seed_inicial():
    """Carga catálogos y usuarios iniciales si la base de datos está vacía."""
    if Departamento.query.first() is None:
        for codigo, nombre in DEPARTAMENTOS_INICIALES:
            db.session.add(Departamento(codigo=codigo, nombre=nombre))
        db.session.commit()

    if TipoDocumento.query.first() is None:
        for prefijo, nombre, descripcion in TIPOS_DOCUMENTO_INICIALES:
            db.session.add(TipoDocumento(prefijo=prefijo, nombre=nombre, descripcion=descripcion))
        db.session.commit()

    if CargoPosicion.query.first() is None:
        for nombre in CARGOS_INICIALES:
            db.session.add(CargoPosicion(nombre=nombre))
        db.session.commit()

    if Usuario.query.first() is None:
        depto_gq = Departamento.query.filter_by(codigo='GQ').first()

        admin = Usuario(
            username='admin',
            email='admin@farach.local',
            nombre_completo='Administrador del Sistema',
            cargo='Administrador',
            rol='admin',
            departamento_id=depto_gq.id if depto_gq else None,
        )
        admin.set_password('farach2025')
        db.session.add(admin)

        gestor = Usuario(
            username='gestor1',
            email='gestor1@farach.local',
            nombre_completo='Gestor Documentación Demo',
            cargo='Gestor Documental',
            rol='gestor_doc',
            departamento_id=depto_gq.id if depto_gq else None,
        )
        gestor.set_password('demo123')
        db.session.add(gestor)

        db.session.commit()
