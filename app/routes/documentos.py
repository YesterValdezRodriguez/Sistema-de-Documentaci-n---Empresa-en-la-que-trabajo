"""Módulo 1 — Gestión de Documentos (sistema FAFII)."""
from datetime import date
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, send_file, current_app, abort)
from flask_login import login_required, current_user
from app.extensions import db
from app.models.documento import Documento, VersionDocumento, DistribucionCopia, ESTADOS_DOCUMENTO
from app.models.config_app import TipoDocumento, Departamento
from app.utils.decorators import rol_requerido
from app.utils.helpers import parse_fecha, registrar_log, incrementar_version
from app.services import pdf_service, excel_service

documentos_bp = Blueprint('documentos', __name__)


def _filtrar_documentos():
    """Aplica filtros de búsqueda comunes a la lista maestra."""
    consulta = Documento.query
    busqueda = request.args.get('q', '').strip()
    tipo_id = request.args.get('tipo', type=int)
    depto_id = request.args.get('departamento', type=int)
    estado = request.args.get('estado', '')

    if busqueda:
        like = f'%{busqueda}%'
        consulta = consulta.filter(db.or_(Documento.codigo.ilike(like),
                                          Documento.titulo.ilike(like)))
    if tipo_id:
        consulta = consulta.filter(Documento.tipo_doc_id == tipo_id)
    if depto_id:
        consulta = consulta.filter(Documento.departamento_id == depto_id)
    if estado:
        consulta = consulta.filter(Documento.estado == estado)
    return consulta.order_by(Documento.codigo.asc())


def _contexto_catalogos():
    return {
        'tipos': TipoDocumento.query.filter_by(activo=True).order_by(TipoDocumento.prefijo).all(),
        'departamentos': Departamento.query.filter_by(activo=True).order_by(Departamento.codigo).all(),
        'estados': ESTADOS_DOCUMENTO,
    }


@documentos_bp.route('/')
@login_required
def lista():
    pagina = request.args.get('pagina', 1, type=int)
    paginacion = _filtrar_documentos().paginate(
        page=pagina, per_page=current_app.config['REGISTROS_POR_PAGINA'], error_out=False)
    return render_template('documentos/lista.html', paginacion=paginacion,
                           documentos=paginacion.items, **_contexto_catalogos())


@documentos_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def nuevo():
    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip().upper()
        if Documento.query.filter_by(codigo=codigo).first():
            flash(f'Ya existe un documento con el código {codigo}.', 'danger')
            return render_template('documentos/form.html', documento=None,
                                   **_contexto_catalogos()), 400

        doc = Documento(
            codigo=codigo,
            titulo=request.form.get('titulo', '').strip(),
            tipo_doc_id=request.form.get('tipo_doc_id', type=int),
            departamento_id=request.form.get('departamento_id', type=int),
            version_actual=request.form.get('version_actual', '01').strip() or '01',
            estado='BORRADOR',
            fecha_emision=parse_fecha(request.form.get('fecha_emision')),
            fecha_vigencia=parse_fecha(request.form.get('fecha_vigencia')),
            fecha_proxima_revision=parse_fecha(request.form.get('fecha_proxima_revision')),
            elaborado_por=request.form.get('elaborado_por', '').strip(),
            revisado_por=request.form.get('revisado_por', '').strip(),
            aprobado_por=request.form.get('aprobado_por', '').strip(),
            descripcion=request.form.get('descripcion', '').strip(),
            alcance=request.form.get('alcance', '').strip(),
            aplica_a=request.form.get('aplica_a', '').strip(),
            ubicacion_fisica=request.form.get('ubicacion_fisica', '').strip(),
            creado_por_id=current_user.id,
        )
        db.session.add(doc)
        db.session.flush()
        db.session.add(VersionDocumento(
            documento_id=doc.id,
            numero_version=doc.version_actual,
            fecha_emision=doc.fecha_emision,
            cambios_realizados='Versión inicial del documento.',
            creado_por_id=current_user.id,
            archivo_nombre=request.form.get('archivo_nombre', '').strip(),
        ))
        db.session.commit()
        registrar_log('CREACION', 'Documentos', f'Documento {doc.codigo} creado')
        flash(f'Documento {doc.codigo} creado en estado Borrador.', 'success')
        return redirect(url_for('documentos.detalle', id=doc.id))

    return render_template('documentos/form.html', documento=None, **_contexto_catalogos())


@documentos_bp.route('/<int:id>')
@login_required
def detalle(id):
    doc = db.get_or_404(Documento, id)
    return render_template('documentos/detalle.html', documento=doc,
                           hoy=date.today(), **_contexto_catalogos())


@documentos_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def editar(id):
    doc = db.get_or_404(Documento, id)
    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip().upper()
        existente = Documento.query.filter(Documento.codigo == codigo,
                                           Documento.id != doc.id).first()
        if existente:
            flash(f'Ya existe otro documento con el código {codigo}.', 'danger')
            return render_template('documentos/form.html', documento=doc,
                                   **_contexto_catalogos()), 400

        doc.codigo = codigo
        doc.titulo = request.form.get('titulo', '').strip()
        doc.tipo_doc_id = request.form.get('tipo_doc_id', type=int)
        doc.departamento_id = request.form.get('departamento_id', type=int)
        doc.fecha_emision = parse_fecha(request.form.get('fecha_emision'))
        doc.fecha_vigencia = parse_fecha(request.form.get('fecha_vigencia'))
        doc.fecha_proxima_revision = parse_fecha(request.form.get('fecha_proxima_revision'))
        doc.elaborado_por = request.form.get('elaborado_por', '').strip()
        doc.revisado_por = request.form.get('revisado_por', '').strip()
        doc.aprobado_por = request.form.get('aprobado_por', '').strip()
        doc.descripcion = request.form.get('descripcion', '').strip()
        doc.alcance = request.form.get('alcance', '').strip()
        doc.aplica_a = request.form.get('aplica_a', '').strip()
        doc.ubicacion_fisica = request.form.get('ubicacion_fisica', '').strip()
        db.session.commit()
        registrar_log('EDICION', 'Documentos', f'Documento {doc.codigo} editado')
        flash('Documento actualizado correctamente.', 'success')
        return redirect(url_for('documentos.detalle', id=doc.id))

    return render_template('documentos/form.html', documento=doc, **_contexto_catalogos())


@documentos_bp.route('/<int:id>/enviar-revision', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def enviar_revision(id):
    doc = db.get_or_404(Documento, id)
    if doc.estado != 'BORRADOR':
        flash('Solo los documentos en Borrador pueden enviarse a revisión.', 'warning')
    else:
        doc.estado = 'EN_REVISION'
        db.session.commit()
        registrar_log('FLUJO', 'Documentos', f'{doc.codigo} enviado a revisión')
        flash(f'Documento {doc.codigo} enviado a revisión.', 'success')
    return redirect(url_for('documentos.detalle', id=id))


@documentos_bp.route('/<int:id>/aprobar', methods=['POST'])
@login_required
@rol_requerido('aprobador')
def aprobar(id):
    doc = db.get_or_404(Documento, id)
    if doc.estado != 'EN_REVISION':
        flash('Solo los documentos En Revisión pueden aprobarse.', 'warning')
    else:
        doc.estado = 'APROBADO'
        if doc.versiones:
            version = doc.versiones[0]
            version.aprobado_por_id = current_user.id
            version.fecha_aprobacion = date.today()
        db.session.commit()
        registrar_log('APROBACION', 'Documentos', f'{doc.codigo} aprobado')
        flash(f'Documento {doc.codigo} aprobado.', 'success')
    return redirect(url_for('documentos.detalle', id=id))


@documentos_bp.route('/<int:id>/publicar', methods=['POST'])
@login_required
@rol_requerido('aprobador', 'gestor_doc')
def publicar(id):
    doc = db.get_or_404(Documento, id)
    if doc.estado != 'APROBADO':
        flash('Solo los documentos Aprobados pueden pasar a Vigente.', 'warning')
    else:
        doc.estado = 'VIGENTE'
        if not doc.fecha_vigencia:
            doc.fecha_vigencia = date.today()
        db.session.commit()
        registrar_log('FLUJO', 'Documentos', f'{doc.codigo} publicado como vigente')
        flash(f'Documento {doc.codigo} ahora está Vigente.', 'success')
    return redirect(url_for('documentos.detalle', id=id))


@documentos_bp.route('/<int:id>/rechazar', methods=['POST'])
@login_required
@rol_requerido('aprobador')
def rechazar(id):
    doc = db.get_or_404(Documento, id)
    if doc.estado != 'EN_REVISION':
        flash('Solo los documentos En Revisión pueden devolverse.', 'warning')
    else:
        doc.estado = 'BORRADOR'
        db.session.commit()
        registrar_log('FLUJO', 'Documentos', f'{doc.codigo} devuelto a borrador')
        flash(f'Documento {doc.codigo} devuelto a Borrador.', 'info')
    return redirect(url_for('documentos.detalle', id=id))


@documentos_bp.route('/<int:id>/nueva-version', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def nueva_version(id):
    doc = db.get_or_404(Documento, id)
    if request.method == 'POST':
        cambios = request.form.get('cambios_realizados', '').strip()
        if not cambios:
            flash('Debe describir los cambios realizados.', 'warning')
            return render_template('documentos/nueva_version.html', documento=doc), 400

        nueva = request.form.get('numero_version', '').strip() or \
            incrementar_version(doc.version_actual)
        doc.version_actual = nueva
        doc.estado = 'EN_REVISION'
        doc.fecha_emision = parse_fecha(request.form.get('fecha_emision')) or date.today()
        db.session.add(VersionDocumento(
            documento_id=doc.id,
            numero_version=nueva,
            fecha_emision=doc.fecha_emision,
            cambios_realizados=cambios,
            creado_por_id=current_user.id,
            archivo_nombre=request.form.get('archivo_nombre', '').strip(),
        ))
        db.session.commit()
        registrar_log('NUEVA_VERSION', 'Documentos', f'{doc.codigo} versión {nueva}')
        flash(f'Versión {nueva} registrada. El documento pasó a revisión.', 'success')
        return redirect(url_for('documentos.detalle', id=doc.id))

    return render_template('documentos/nueva_version.html', documento=doc,
                           version_sugerida=incrementar_version(doc.version_actual))


@documentos_bp.route('/<int:id>/dar-baja', methods=['POST'])
@login_required
@rol_requerido('gestor_doc', 'aprobador')
def dar_baja(id):
    doc = db.get_or_404(Documento, id)
    motivo = request.form.get('motivo_baja', '').strip()
    if not motivo:
        flash('Debe indicar el motivo de la baja.', 'warning')
        return redirect(url_for('documentos.detalle', id=id))
    doc.estado = 'OBSOLETO'
    doc.motivo_baja = motivo
    doc.fecha_baja = date.today()
    db.session.commit()
    registrar_log('BAJA', 'Documentos', f'{doc.codigo} dado de baja: {motivo}')
    flash(f'Documento {doc.codigo} marcado como Obsoleto.', 'success')
    return redirect(url_for('documentos.detalle', id=id))


# ------------------------------------------------------- Copias controladas

@documentos_bp.route('/copias')
@login_required
def copias():
    pagina = request.args.get('pagina', 1, type=int)
    consulta = (DistribucionCopia.query
                .filter_by(activo=True)
                .join(Documento)
                .order_by(Documento.codigo, DistribucionCopia.numero_copia))
    doc_id = request.args.get('documento_id', type=int)
    if doc_id:
        consulta = consulta.filter(DistribucionCopia.documento_id == doc_id)
    paginacion = consulta.paginate(
        page=pagina, per_page=current_app.config['REGISTROS_POR_PAGINA'], error_out=False)
    documentos = Documento.query.filter_by(activo=True).order_by(Documento.codigo).all()
    return render_template('documentos/copias.html', paginacion=paginacion,
                           copias=paginacion.items, documentos=documentos)


@documentos_bp.route('/<int:id>/copias/nueva', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def nueva_copia(id):
    doc = db.get_or_404(Documento, id)
    if request.method == 'POST':
        copia = DistribucionCopia(
            documento_id=doc.id,
            numero_copia=request.form.get('numero_copia', type=int) or 1,
            destinatario=request.form.get('destinatario', '').strip(),
            departamento_id=request.form.get('departamento_id', type=int),
            fecha_entrega=parse_fecha(request.form.get('fecha_entrega')),
            entregado_por_id=current_user.id,
            firmado=bool(request.form.get('firmado')),
            fecha_firma=parse_fecha(request.form.get('fecha_firma')),
            observaciones=request.form.get('observaciones', '').strip(),
        )
        db.session.add(copia)
        doc.numero_copias_controladas = (doc.numero_copias_controladas or 0) + 1
        db.session.commit()
        registrar_log('CREACION', 'Documentos',
                      f'Copia controlada #{copia.numero_copia} de {doc.codigo}')
        flash('Copia controlada registrada.', 'success')
        return redirect(url_for('documentos.detalle', id=doc.id))

    siguiente = (db.session.query(db.func.max(DistribucionCopia.numero_copia))
                 .filter_by(documento_id=doc.id).scalar() or 0) + 1
    departamentos = Departamento.query.filter_by(activo=True).order_by(Departamento.codigo).all()
    return render_template('documentos/copia_form.html', documento=doc,
                           siguiente_copia=siguiente, departamentos=departamentos)


@documentos_bp.route('/copias/<int:id>/firmar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def firmar_copia(id):
    copia = db.get_or_404(DistribucionCopia, id)
    copia.firmado = True
    copia.fecha_firma = date.today()
    db.session.commit()
    registrar_log('EDICION', 'Documentos',
                  f'Firma de copia #{copia.numero_copia} de {copia.documento.codigo}')
    flash('Copia marcada como firmada.', 'success')
    return redirect(request.referrer or url_for('documentos.copias'))


@documentos_bp.route('/copias/<int:id>/retirar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def retirar_copia(id):
    copia = db.get_or_404(DistribucionCopia, id)
    copia.activo = False
    doc = copia.documento
    doc.numero_copias_controladas = max((doc.numero_copias_controladas or 1) - 1, 0)
    db.session.commit()
    registrar_log('BAJA', 'Documentos',
                  f'Retiro de copia #{copia.numero_copia} de {doc.codigo}')
    flash('Copia controlada retirada.', 'success')
    return redirect(request.referrer or url_for('documentos.copias'))


# ----------------------------------------------------------------- Reportes

@documentos_bp.route('/exportar/excel')
@login_required
def exportar_excel():
    documentos = _filtrar_documentos().all()
    filas = [[d.codigo, d.titulo,
              d.tipo_doc.nombre if d.tipo_doc else '',
              d.departamento.nombre if d.departamento else '',
              d.version_actual, d.estado_nombre,
              d.fecha_emision.strftime('%d/%m/%Y') if d.fecha_emision else '',
              d.fecha_vigencia.strftime('%d/%m/%Y') if d.fecha_vigencia else '',
              d.fecha_proxima_revision.strftime('%d/%m/%Y') if d.fecha_proxima_revision else '',
              d.elaborado_por or '', d.revisado_por or '', d.aprobado_por or '',
              d.ubicacion_fisica or '', d.numero_copias_controladas or 0]
             for d in documentos]
    archivo = excel_service.exportar_excel(
        'Lista Maestra de Documentos', 'Lista Maestra',
        ['Código', 'Título', 'Tipo', 'Departamento', 'Versión', 'Estado',
         'Emisión', 'Vigencia', 'Próx. Revisión', 'Elaborado por', 'Revisado por',
         'Aprobado por', 'Ubicación física', 'Copias'],
        filas)
    registrar_log('EXPORTACION', 'Documentos', 'Lista maestra exportada a Excel')
    return send_file(archivo, as_attachment=True,
                     download_name='lista_maestra_documentos.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@documentos_bp.route('/<int:id>/pdf')
@login_required
def ficha_pdf(id):
    doc = db.get_or_404(Documento, id)
    archivo = pdf_service.pdf_ficha_documento(doc)
    return send_file(archivo, as_attachment=True,
                     download_name=f'ficha_{doc.codigo}.pdf', mimetype='application/pdf')


@documentos_bp.route('/lista-maestra/pdf')
@login_required
def lista_maestra_pdf():
    documentos = _filtrar_documentos().all()
    archivo = pdf_service.pdf_lista_maestra(documentos)
    return send_file(archivo, as_attachment=True,
                     download_name='lista_maestra_documentos.pdf', mimetype='application/pdf')
