"""Cálculo de alertas visuales para el dashboard (sin email)."""
from datetime import date, timedelta
from app.models.documento import Documento
from app.models.capa import CAPA
from app.models.cambio import SolicitudCambio
from app.models.capacitacion import SesionCapacitacion


def documentos_por_vencer(dias=30, limite=None):
    """Documentos vigentes cuya próxima revisión vence en <= `dias` días."""
    hoy = date.today()
    tope = hoy + timedelta(days=dias)
    consulta = (Documento.query
                .filter(Documento.estado == 'VIGENTE',
                        Documento.activo.is_(True),
                        Documento.fecha_proxima_revision.isnot(None),
                        Documento.fecha_proxima_revision <= tope)
                .order_by(Documento.fecha_proxima_revision.asc()))
    if limite:
        consulta = consulta.limit(limite)
    return consulta.all()


def capas_vencidas_o_inmediatas(dias=7):
    """CAPAs vencidas o con fecha límite en <= `dias` días."""
    hoy = date.today()
    tope = hoy + timedelta(days=dias)
    return (CAPA.query
            .filter(CAPA.estado.notin_(['CERRADA']),
                    CAPA.fecha_limite_implementacion.isnot(None),
                    CAPA.fecha_limite_implementacion <= tope)
            .order_by(CAPA.fecha_limite_implementacion.asc())
            .all())


def solicitudes_cambio_antiguas(dias=30):
    """Solicitudes de cambio abiertas hace más de `dias` días."""
    corte = date.today() - timedelta(days=dias)
    return (SolicitudCambio.query
            .filter(SolicitudCambio.estado.in_(['ABIERTA', 'EN_EVALUACION']),
                    SolicitudCambio.fecha_solicitud <= corte)
            .order_by(SolicitudCambio.fecha_solicitud.asc())
            .all())


def sesiones_proximas(dias=7):
    """Sesiones de capacitación programadas en los próximos `dias` días."""
    hoy = date.today()
    tope = hoy + timedelta(days=dias)
    return (SesionCapacitacion.query
            .filter(SesionCapacitacion.estado == 'PROGRAMADA',
                    SesionCapacitacion.fecha_sesion >= hoy,
                    SesionCapacitacion.fecha_sesion <= tope)
            .order_by(SesionCapacitacion.fecha_sesion.asc())
            .all())
