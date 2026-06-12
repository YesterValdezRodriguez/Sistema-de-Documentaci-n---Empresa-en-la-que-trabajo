"""Funciones utilitarias compartidas."""
from datetime import datetime, date
from flask import request
from flask_login import current_user
from app.extensions import db
from app.models.config_app import LogSistema


def parse_fecha(valor):
    """Convierte un string de formulario (YYYY-MM-DD del input date) en date."""
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except ValueError:
        try:
            return datetime.strptime(valor, '%d/%m/%Y').date()
        except ValueError:
            return None


def formato_fecha(valor):
    """Filtro Jinja: fecha en formato DD/MM/AAAA."""
    if not valor:
        return '—'
    if isinstance(valor, datetime):
        valor = valor.date()
    return valor.strftime('%d/%m/%Y')


def formato_fecha_hora(valor):
    """Filtro Jinja: fecha y hora DD/MM/AAAA HH:MM."""
    if not valor:
        return '—'
    return valor.strftime('%d/%m/%Y %H:%M')


BADGES_ESTADO = {
    # Documentos
    'BORRADOR': 'secondary', 'EN_REVISION': 'info', 'APROBADO': 'primary',
    'VIGENTE': 'success', 'OBSOLETO': 'dark',
    # Solicitudes de cambio
    'ABIERTA': 'warning', 'EN_EVALUACION': 'info', 'APROBADA': 'primary',
    'RECHAZADA': 'danger', 'IMPLEMENTADA': 'success', 'CERRADA': 'dark',
    # CAPA
    'EN_PROCESO': 'info', 'VERIFICACION': 'primary', 'VENCIDA': 'danger',
    # Auditorías
    'PLANIFICADA': 'secondary', 'EN_CURSO': 'info', 'INFORME_PENDIENTE': 'warning',
    # Hallazgos / acciones
    'ABIERTO': 'warning', 'CERRADO': 'dark', 'PENDIENTE': 'secondary', 'COMPLETADA': 'success',
    # Sesiones
    'PROGRAMADA': 'info', 'REALIZADA': 'success', 'CANCELADA': 'danger',
    # Prioridades
    'ALTA': 'danger', 'MEDIA': 'warning', 'BAJA': 'secondary',
}


def badge_estado(estado):
    """Filtro Jinja: clase de color Bootstrap para un estado."""
    return BADGES_ESTADO.get(estado, 'secondary')


def generar_numero(modelo, campo, prefijo):
    """Genera numeración automática tipo PREFIJO-YYYY-NNN (ej. CAPA-2025-001)."""
    anio = date.today().year
    patron = f'{prefijo}-{anio}-%'
    columna = getattr(modelo, campo)
    ultimo = (db.session.query(columna)
              .filter(columna.like(patron))
              .order_by(columna.desc())
              .first())
    if ultimo:
        try:
            secuencia = int(ultimo[0].rsplit('-', 1)[1]) + 1
        except (ValueError, IndexError):
            secuencia = 1
    else:
        secuencia = 1
    return f'{prefijo}-{anio}-{secuencia:03d}'


def registrar_log(accion, modulo, descripcion=''):
    """Registra una acción en el log de auditoría del sistema."""
    log = LogSistema(
        usuario_id=current_user.id if current_user.is_authenticated else None,
        accion=accion,
        modulo=modulo,
        descripcion=descripcion,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(log)
    db.session.commit()


def incrementar_version(version_actual):
    """Incrementa una versión numérica tipo '03' -> '04'."""
    try:
        return f'{int(version_actual) + 1:02d}'
    except (ValueError, TypeError):
        return '01'
