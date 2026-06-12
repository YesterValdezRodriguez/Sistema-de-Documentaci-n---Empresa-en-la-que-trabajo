"""Módulo 6 — Dashboard principal con indicadores y gráficos."""
from datetime import date, timedelta
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from app.extensions import db
from app.models.documento import Documento
from app.models.capa import CAPA
from app.models.cambio import SolicitudCambio
from app.models.capacitacion import SesionCapacitacion
from app.models.auditoria import Auditoria
from app.models.config_app import Departamento
from app.services import notificacion_service

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)

    # ----- Tarjetas de indicadores -----
    total_documentos = Documento.query.filter_by(activo=True).count()
    docs_vigentes = Documento.query.filter_by(estado='VIGENTE', activo=True).count()
    docs_por_vencer = len(notificacion_service.documentos_por_vencer(30))
    docs_obsoletos_mes = Documento.query.filter(
        Documento.estado == 'OBSOLETO',
        Documento.fecha_baja.isnot(None),
        Documento.fecha_baja >= inicio_mes).count()

    capas_abiertas = CAPA.query.filter(CAPA.estado.notin_(['CERRADA'])).count()
    capas_vencidas = CAPA.query.filter(
        CAPA.estado.notin_(['CERRADA']),
        CAPA.fecha_limite_implementacion.isnot(None),
        CAPA.fecha_limite_implementacion < hoy).count()

    sc_en_evaluacion = SolicitudCambio.query.filter(
        SolicitudCambio.estado.in_(['ABIERTA', 'EN_EVALUACION'])).count()

    sesiones_proximas = len(notificacion_service.sesiones_proximas(7))
    auditorias_en_curso = Auditoria.query.filter_by(estado='EN_CURSO').count()

    # ----- Gráfico: documentos por departamento -----
    docs_por_depto = (db.session.query(Departamento.codigo, func.count(Documento.id))
                      .join(Documento, Documento.departamento_id == Departamento.id)
                      .filter(Documento.activo.is_(True))
                      .group_by(Departamento.codigo)
                      .order_by(Departamento.codigo)
                      .all())

    # ----- Gráfico: CAPAs por estado -----
    capas_por_estado = (db.session.query(CAPA.estado, func.count(CAPA.id))
                        .group_by(CAPA.estado).all())

    # ----- Gráfico: documentos creados por mes (últimos 6 meses) -----
    meses_labels, meses_valores = [], []
    for i in range(5, -1, -1):
        anio = hoy.year
        mes = hoy.month - i
        while mes <= 0:
            mes += 12
            anio -= 1
        inicio = date(anio, mes, 1)
        fin = date(anio + (1 if mes == 12 else 0), 1 if mes == 12 else mes + 1, 1)
        cantidad = Documento.query.filter(
            Documento.fecha_creacion >= inicio,
            Documento.fecha_creacion < fin).count()
        meses_labels.append(inicio.strftime('%m/%Y'))
        meses_valores.append(cantidad)

    # ----- Alertas -----
    alertas_docs = notificacion_service.documentos_por_vencer(30, limite=10)
    alertas_capas = notificacion_service.capas_vencidas_o_inmediatas(7)
    alertas_sc = notificacion_service.solicitudes_cambio_antiguas(30)

    return render_template(
        'dashboard/index.html',
        hoy=hoy,
        total_documentos=total_documentos,
        docs_vigentes=docs_vigentes,
        docs_por_vencer=docs_por_vencer,
        docs_obsoletos_mes=docs_obsoletos_mes,
        capas_abiertas=capas_abiertas,
        capas_vencidas=capas_vencidas,
        sc_en_evaluacion=sc_en_evaluacion,
        sesiones_proximas=sesiones_proximas,
        auditorias_en_curso=auditorias_en_curso,
        grafico_deptos_labels=[d[0] for d in docs_por_depto],
        grafico_deptos_valores=[d[1] for d in docs_por_depto],
        grafico_capas_labels=[c[0] for c in capas_por_estado],
        grafico_capas_valores=[c[1] for c in capas_por_estado],
        grafico_meses_labels=meses_labels,
        grafico_meses_valores=meses_valores,
        alertas_docs=alertas_docs,
        alertas_capas=alertas_capas,
        alertas_sc=alertas_sc,
    )
