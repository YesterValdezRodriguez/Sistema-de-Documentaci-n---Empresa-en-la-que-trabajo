"""Módulo — Armado de Expedientes (Batch Records / Fórmulas Maestras).

Flujo general:

1. Cargar **archivos fuente** (PDF) con versiones: fórmulas maestras, registros…
2. Crear una **plantilla** (configuración) y armarla de forma interactiva:
   agregar registros, ordenarlos, elegir páginas y el paso donde van.
3. **Generar** el expediente de un lote (con sellos/foliado) y descargarlo o
   guardarlo. Cuando un registro se actualiza, basta subir su versión nueva y
   **regenerar** el expediente. También se puede **duplicar** una plantilla para
   guardar el armado como una configuración más.
"""
import re
from datetime import date, datetime
from io import BytesIO

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, send_file, jsonify)
from flask_login import login_required, current_user

from app.extensions import db
from app.models.expediente import (
    ArchivoFuente, VersionArchivo, PlantillaExpediente, ItemPlantilla,
    Expediente, TIPOS_ARCHIVO, TIPOS_ARCHIVO_NOMBRES, POSICIONES,
    POSICIONES_NOMBRES)
from app.models.config_app import Departamento
from app.utils.decorators import rol_requerido
from app.utils.helpers import parse_fecha, registrar_log, incrementar_version
from app.services import expediente_service as svc

expedientes_bp = Blueprint('expedientes', __name__)


# ----------------------------------------------------------------- utilidades

def _leer_pdf_subido(campo='archivo'):
    """Lee y valida un PDF subido. Devuelve (datos, nombre_original, error)."""
    f = request.files.get(campo)
    if not f or not f.filename:
        return None, None, 'Debe seleccionar un archivo PDF.'
    datos = f.read()
    if not datos:
        return None, None, 'El archivo está vacío.'
    if not svc.es_pdf_valido(datos):
        return None, None, 'El archivo no es un PDF válido o está dañado.'
    return datos, f.filename, None


def _slug(texto):
    texto = re.sub(r'[^\w\-. ]', '', (texto or '').strip()).replace(' ', '_')
    return texto or 'expediente'


def _nombre_descarga(codigo, nombre, lote=None, sufijo=''):
    base = _slug(codigo or nombre)
    if lote:
        base += f'_lote_{_slug(lote)}'
    return f'{base}{sufijo}.pdf'


# =====================================================================
#  ARCHIVOS FUENTE (PDF reutilizables con versiones)
# =====================================================================

@expedientes_bp.route('/archivos')
@login_required
def archivos():
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '')
    consulta = ArchivoFuente.query.filter_by(activo=True)
    if q:
        like = f'%{q}%'
        consulta = consulta.filter(db.or_(ArchivoFuente.nombre.ilike(like),
                                          ArchivoFuente.codigo.ilike(like)))
    if tipo:
        consulta = consulta.filter(ArchivoFuente.tipo == tipo)
    lista = consulta.order_by(ArchivoFuente.tipo, ArchivoFuente.nombre).all()
    return render_template('expedientes/archivos.html', archivos=lista,
                           tipos=TIPOS_ARCHIVO, tipos_nombres=TIPOS_ARCHIVO_NOMBRES)


@expedientes_bp.route('/archivos/nuevo', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def archivo_nuevo():
    if request.method == 'POST':
        datos, nombre_orig, err = _leer_pdf_subido()
        if err:
            flash(err, 'danger')
            return redirect(request.url)
        archivo = ArchivoFuente(
            nombre=request.form.get('nombre', '').strip() or nombre_orig,
            codigo=request.form.get('codigo', '').strip(),
            tipo=request.form.get('tipo', 'REGISTRO'),
            descripcion=request.form.get('descripcion', '').strip(),
            departamento_id=request.form.get('departamento_id', type=int),
            creado_por_id=current_user.id,
        )
        db.session.add(archivo)
        db.session.flush()
        version = VersionArchivo(
            archivo_id=archivo.id,
            numero_version=request.form.get('numero_version', '01').strip() or '01',
            descripcion_cambio='Versión inicial.',
            nombre_original=nombre_orig,
            datos=datos,
            num_paginas=svc.contar_paginas(datos),
            tamano_bytes=len(datos),
            creado_por_id=current_user.id,
        )
        db.session.add(version)
        db.session.flush()
        archivo.version_actual_id = version.id
        db.session.commit()
        registrar_log('CREACION', 'Expedientes',
                      f'Archivo fuente «{archivo.nombre}» cargado')
        flash(f'Archivo «{archivo.nombre}» cargado ({version.num_paginas} pág.).',
              'success')
        return redirect(url_for('expedientes.archivo_detalle', id=archivo.id))

    departamentos = Departamento.query.filter_by(activo=True).order_by(
        Departamento.codigo).all()
    return render_template('expedientes/archivo_form.html',
                           tipos=TIPOS_ARCHIVO, tipos_nombres=TIPOS_ARCHIVO_NOMBRES,
                           departamentos=departamentos)


@expedientes_bp.route('/archivos/<int:id>')
@login_required
def archivo_detalle(id):
    archivo = db.get_or_404(ArchivoFuente, id)
    return render_template('expedientes/archivo_detalle.html', archivo=archivo,
                           tipos_nombres=TIPOS_ARCHIVO_NOMBRES)


@expedientes_bp.route('/archivos/<int:id>/version', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def archivo_nueva_version(id):
    archivo = db.get_or_404(ArchivoFuente, id)
    datos, nombre_orig, err = _leer_pdf_subido()
    if err:
        flash(err, 'danger')
        return redirect(url_for('expedientes.archivo_detalle', id=id))
    ultima = archivo.versiones[0] if archivo.versiones else None
    numero = (request.form.get('numero_version', '').strip()
              or incrementar_version(ultima.numero_version if ultima else '00'))
    version = VersionArchivo(
        archivo_id=archivo.id,
        numero_version=numero,
        descripcion_cambio=request.form.get('descripcion_cambio', '').strip(),
        nombre_original=nombre_orig,
        datos=datos,
        num_paginas=svc.contar_paginas(datos),
        tamano_bytes=len(datos),
        creado_por_id=current_user.id,
    )
    db.session.add(version)
    db.session.flush()
    archivo.version_actual_id = version.id
    db.session.commit()
    registrar_log('NUEVA_VERSION', 'Expedientes', f'{archivo.nombre} v{numero}')
    flash(f'Versión {numero} cargada y marcada como actual. Los expedientes que '
          f'usan «versión actual» tomarán esta versión al regenerarse.', 'success')
    return redirect(url_for('expedientes.archivo_detalle', id=id))


@expedientes_bp.route('/version/<int:id>/marcar-actual', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def version_marcar_actual(id):
    version = db.get_or_404(VersionArchivo, id)
    archivo = version.archivo
    archivo.version_actual_id = version.id
    db.session.commit()
    registrar_log('EDICION', 'Expedientes',
                  f'{archivo.nombre}: versión actual fijada en v{version.numero_version}')
    flash(f'La versión {version.numero_version} es ahora la versión actual.', 'success')
    return redirect(url_for('expedientes.archivo_detalle', id=archivo.id))


@expedientes_bp.route('/version/<int:id>/ver')
@login_required
def version_ver(id):
    version = db.get_or_404(VersionArchivo, id)
    nombre = _nombre_descarga(version.archivo.codigo, version.archivo.nombre,
                              sufijo=f'_v{version.numero_version}')
    return send_file(BytesIO(version.datos or b''), mimetype='application/pdf',
                     as_attachment=bool(request.args.get('descargar')),
                     download_name=nombre)


@expedientes_bp.route('/archivos/<int:id>/eliminar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def archivo_eliminar(id):
    archivo = db.get_or_404(ArchivoFuente, id)
    en_uso = ItemPlantilla.query.filter_by(archivo_id=id).count()
    if en_uso:
        flash(f'No se puede eliminar: el archivo se usa en {en_uso} registro(s) de '
              f'plantillas. Quítelo de esas plantillas primero.', 'warning')
        return redirect(url_for('expedientes.archivo_detalle', id=id))
    nombre = archivo.nombre
    db.session.delete(archivo)
    db.session.commit()
    registrar_log('BAJA', 'Expedientes', f'Archivo fuente «{nombre}» eliminado')
    flash('Archivo eliminado.', 'success')
    return redirect(url_for('expedientes.archivos'))


# =====================================================================
#  PLANTILLAS (configuraciones guardadas)
# =====================================================================

@expedientes_bp.route('/')
@login_required
def plantillas():
    q = request.args.get('q', '').strip()
    consulta = PlantillaExpediente.query.filter_by(activo=True)
    if q:
        like = f'%{q}%'
        consulta = consulta.filter(db.or_(
            PlantillaExpediente.nombre.ilike(like),
            PlantillaExpediente.producto.ilike(like),
            PlantillaExpediente.codigo.ilike(like)))
    lista = consulta.order_by(PlantillaExpediente.nombre).all()
    return render_template('expedientes/plantillas.html', plantillas=lista)


@expedientes_bp.route('/plantilla/nueva', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def plantilla_nueva():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre de la plantilla es obligatorio.', 'danger')
            return render_template('expedientes/plantilla_form.html', plantilla=None), 400
        p = PlantillaExpediente(
            nombre=nombre,
            producto=request.form.get('producto', '').strip(),
            codigo=request.form.get('codigo', '').strip(),
            version=request.form.get('version', '01').strip() or '01',
            descripcion=request.form.get('descripcion', '').strip(),
            creado_por_id=current_user.id,
        )
        db.session.add(p)
        db.session.commit()
        registrar_log('CREACION', 'Expedientes', f'Plantilla «{p.nombre}» creada')
        flash('Plantilla creada. Ahora agregue los registros que la componen.', 'success')
        return redirect(url_for('expedientes.builder', id=p.id))
    return render_template('expedientes/plantilla_form.html', plantilla=None)


@expedientes_bp.route('/plantilla/<int:id>')
@login_required
def builder(id):
    plantilla = db.get_or_404(PlantillaExpediente, id)
    archivos = ArchivoFuente.query.filter_by(activo=True).order_by(
        ArchivoFuente.tipo, ArchivoFuente.nombre).all()
    return render_template('expedientes/builder.html', plantilla=plantilla,
                           archivos=archivos, posiciones=POSICIONES,
                           posiciones_nombres=POSICIONES_NOMBRES,
                           tipos_nombres=TIPOS_ARCHIVO_NOMBRES, hoy=date.today())


@expedientes_bp.route('/plantilla/<int:id>/editar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def plantilla_editar(id):
    p = db.get_or_404(PlantillaExpediente, id)
    nombre = request.form.get('nombre', '').strip()
    if not nombre:
        flash('El nombre de la plantilla es obligatorio.', 'danger')
        return redirect(url_for('expedientes.builder', id=id))
    p.nombre = nombre
    p.producto = request.form.get('producto', '').strip()
    p.codigo = request.form.get('codigo', '').strip()
    p.version = request.form.get('version', '01').strip() or '01'
    p.descripcion = request.form.get('descripcion', '').strip()
    db.session.commit()
    registrar_log('EDICION', 'Expedientes', f'Plantilla «{p.nombre}» actualizada')
    flash('Datos de la plantilla guardados.', 'success')
    return redirect(url_for('expedientes.builder', id=id))


@expedientes_bp.route('/plantilla/<int:id>/sellos', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def plantilla_sellos(id):
    p = db.get_or_404(PlantillaExpediente, id)
    p.foliar = bool(request.form.get('foliar'))
    p.formato_folio = request.form.get('formato_folio', '').strip()
    p.posicion_folio = request.form.get('posicion_folio', 'INF_DER')
    p.mostrar_encabezado = bool(request.form.get('mostrar_encabezado'))
    p.formato_encabezado = request.form.get('formato_encabezado', '').strip()
    p.posicion_encabezado = request.form.get('posicion_encabezado', 'SUP_CEN')
    p.texto_sello = request.form.get('texto_sello', '').strip()
    p.posicion_sello = request.form.get('posicion_sello', 'SUP_DER')
    db.session.commit()
    registrar_log('EDICION', 'Expedientes', f'Sellos de «{p.nombre}» actualizados')
    flash('Opciones de sellado/foliado guardadas.', 'success')
    return redirect(url_for('expedientes.builder', id=id))


@expedientes_bp.route('/plantilla/<int:id>/duplicar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def plantilla_duplicar(id):
    p = db.get_or_404(PlantillaExpediente, id)
    copia = PlantillaExpediente(
        nombre=request.form.get('nombre', '').strip() or f'{p.nombre} (copia)',
        producto=p.producto, codigo=p.codigo, version=p.version,
        descripcion=p.descripcion, foliar=p.foliar, formato_folio=p.formato_folio,
        posicion_folio=p.posicion_folio, mostrar_encabezado=p.mostrar_encabezado,
        formato_encabezado=p.formato_encabezado, posicion_encabezado=p.posicion_encabezado,
        texto_sello=p.texto_sello, posicion_sello=p.posicion_sello,
        creado_por_id=current_user.id,
    )
    db.session.add(copia)
    db.session.flush()
    for it in sorted(p.items, key=lambda x: x.orden):
        db.session.add(ItemPlantilla(
            plantilla_id=copia.id, orden=it.orden, archivo_id=it.archivo_id,
            usar_version_actual=it.usar_version_actual, version_fija_id=it.version_fija_id,
            rango_paginas=it.rango_paginas, paso=it.paso, titulo=it.titulo,
            sellar_paso=it.sellar_paso))
    db.session.commit()
    registrar_log('CREACION', 'Expedientes',
                  f'Plantilla «{copia.nombre}» duplicada de «{p.nombre}»')
    flash('Configuración guardada como una nueva plantilla.', 'success')
    return redirect(url_for('expedientes.builder', id=copia.id))


@expedientes_bp.route('/plantilla/<int:id>/eliminar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def plantilla_eliminar(id):
    p = db.get_or_404(PlantillaExpediente, id)
    nombre = p.nombre
    Expediente.query.filter_by(plantilla_id=id).update({'plantilla_id': None})
    db.session.delete(p)
    db.session.commit()
    registrar_log('BAJA', 'Expedientes', f'Plantilla «{nombre}» eliminada')
    flash('Plantilla eliminada.', 'success')
    return redirect(url_for('expedientes.plantillas'))


# ----------------------------------------------------- ítems de la plantilla

@expedientes_bp.route('/plantilla/<int:id>/item', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def item_agregar(id):
    db.get_or_404(PlantillaExpediente, id)
    archivo_id = request.form.get('archivo_id', type=int)
    archivo = db.session.get(ArchivoFuente, archivo_id) if archivo_id else None
    if not archivo:
        flash('Seleccione un archivo válido.', 'danger')
        return redirect(url_for('expedientes.builder', id=id))
    rango = request.form.get('rango_paginas', '').strip()
    err = svc.validar_rango(rango)
    if err:
        flash(err, 'danger')
        return redirect(url_for('expedientes.builder', id=id))
    max_orden = db.session.query(db.func.max(ItemPlantilla.orden)).filter_by(
        plantilla_id=id).scalar()
    item = ItemPlantilla(
        plantilla_id=id,
        orden=(max_orden + 1) if max_orden is not None else 0,
        archivo_id=archivo_id,
        rango_paginas=rango,
        paso=request.form.get('paso', '').strip(),
        titulo=request.form.get('titulo', '').strip(),
        sellar_paso=bool(request.form.get('sellar_paso')),
        usar_version_actual=True,
    )
    db.session.add(item)
    db.session.commit()
    flash(f'Registro «{archivo.nombre}» agregado al expediente.', 'success')
    return redirect(url_for('expedientes.builder', id=id))


@expedientes_bp.route('/item/<int:id>/editar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def item_editar(id):
    item = db.get_or_404(ItemPlantilla, id)
    rango = request.form.get('rango_paginas', '').strip()
    err = svc.validar_rango(rango)
    if err:
        flash(err, 'danger')
        return redirect(url_for('expedientes.builder', id=item.plantilla_id))
    item.rango_paginas = rango
    item.paso = request.form.get('paso', '').strip()
    item.titulo = request.form.get('titulo', '').strip()
    item.sellar_paso = bool(request.form.get('sellar_paso'))
    usar_actual = bool(request.form.get('usar_version_actual'))
    item.usar_version_actual = usar_actual
    item.version_fija_id = (None if usar_actual
                            else request.form.get('version_fija_id', type=int))
    db.session.commit()
    flash('Registro actualizado.', 'success')
    return redirect(url_for('expedientes.builder', id=item.plantilla_id))


@expedientes_bp.route('/item/<int:id>/eliminar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def item_eliminar(id):
    item = db.get_or_404(ItemPlantilla, id)
    pid = item.plantilla_id
    db.session.delete(item)
    db.session.commit()
    flash('Registro quitado del expediente.', 'info')
    return redirect(url_for('expedientes.builder', id=pid))


@expedientes_bp.route('/item/<int:id>/mover/<direccion>', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def item_mover(id, direccion):
    item = db.get_or_404(ItemPlantilla, id)
    items = sorted(item.plantilla.items, key=lambda it: it.orden)
    idx = items.index(item)
    destino = idx - 1 if direccion == 'subir' else idx + 1
    if 0 <= destino < len(items):
        items[idx].orden, items[destino].orden = items[destino].orden, items[idx].orden
        db.session.commit()
    return redirect(url_for('expedientes.builder', id=item.plantilla_id))


@expedientes_bp.route('/plantilla/<int:id>/reordenar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def plantilla_reordenar(id):
    p = db.get_or_404(PlantillaExpediente, id)
    payload = request.get_json(silent=True) or {}
    ids = payload.get('orden', [])
    mapa = {it.id: it for it in p.items}
    pos = 0
    for item_id in ids:
        try:
            it = mapa.get(int(item_id))
        except (TypeError, ValueError):
            it = None
        if it:
            it.orden = pos
            pos += 1
    db.session.commit()
    return jsonify(ok=True, total=pos)


# ----------------------------------------------------- vista previa / armado

@expedientes_bp.route('/plantilla/<int:id>/preview.pdf')
@login_required
def plantilla_preview(id):
    p = db.get_or_404(PlantillaExpediente, id)
    contexto = {
        'lote': request.args.get('lote', '(LOTE)'),
        'producto': p.producto,
        'codigo': p.codigo,
        'fecha': date.today().strftime('%d/%m/%Y'),
        'version': p.version,
    }
    buf, n = svc.ensamblar(p, contexto)
    if n == 0:
        buf = svc.pdf_mensaje('La plantilla no tiene registros con páginas. '
                              'Agregue registros para ver la vista previa.')
    return send_file(buf, mimetype='application/pdf', as_attachment=False,
                     download_name=f'preview_{p.id}.pdf', max_age=0)


@expedientes_bp.route('/plantilla/<int:id>/generar', methods=['GET', 'POST'])
@login_required
@rol_requerido('gestor_doc')
def plantilla_generar(id):
    p = db.get_or_404(PlantillaExpediente, id)
    if request.method == 'POST':
        lote = request.form.get('numero_lote', '').strip()
        producto = request.form.get('producto', '').strip() or p.producto
        codigo = request.form.get('codigo', '').strip() or p.codigo
        fecha = parse_fecha(request.form.get('fecha_expediente')) or date.today()
        contexto = {'lote': lote, 'producto': producto, 'codigo': codigo,
                    'fecha': fecha.strftime('%d/%m/%Y'), 'version': p.version}
        buf, n = svc.ensamblar(p, contexto)
        if n == 0:
            flash('La plantilla no tiene registros con páginas. Agregue registros '
                  'antes de generar el expediente.', 'warning')
            return redirect(url_for('expedientes.builder', id=id))
        data = buf.getvalue()
        accion = request.form.get('accion', 'descargar')
        if accion in ('guardar', 'guardar_descargar'):
            nombre = request.form.get('nombre', '').strip()
            if not nombre:
                nombre = f'{p.nombre} — Lote {lote}' if lote else p.nombre
            exp = Expediente(
                plantilla_id=p.id, nombre=nombre,
                producto=producto, codigo=codigo, numero_lote=lote,
                fecha_expediente=fecha, datos=data, num_paginas=n,
                tamano_bytes=len(data), generado_por_id=current_user.id)
            db.session.add(exp)
            db.session.commit()
            registrar_log('GENERACION', 'Expedientes',
                          f'Expediente «{exp.nombre}» generado ({n} pág.)')
            flash(f'Expediente armado y guardado ({n} páginas).', 'success')
            if accion == 'guardar':
                return redirect(url_for('expedientes.armado_detalle', id=exp.id))
            return send_file(BytesIO(data), mimetype='application/pdf',
                             as_attachment=True,
                             download_name=_nombre_descarga(codigo, p.nombre, lote))
        registrar_log('GENERACION', 'Expedientes',
                      f'Expediente de «{p.nombre}» descargado (sin guardar)')
        return send_file(BytesIO(data), mimetype='application/pdf', as_attachment=True,
                         download_name=_nombre_descarga(codigo, p.nombre, lote))
    return render_template('expedientes/generar.html', plantilla=p, hoy=date.today())


# =====================================================================
#  EXPEDIENTES ARMADOS (PDF generados, por lote)
# =====================================================================

@expedientes_bp.route('/armados')
@login_required
def armados():
    q = request.args.get('q', '').strip()
    consulta = Expediente.query
    if q:
        like = f'%{q}%'
        consulta = consulta.filter(db.or_(
            Expediente.nombre.ilike(like), Expediente.numero_lote.ilike(like),
            Expediente.codigo.ilike(like), Expediente.producto.ilike(like)))
    lista = consulta.order_by(Expediente.fecha_generacion.desc()).all()
    return render_template('expedientes/armados.html', expedientes=lista)


@expedientes_bp.route('/armado/<int:id>')
@login_required
def armado_detalle(id):
    exp = db.get_or_404(Expediente, id)
    return render_template('expedientes/armado_detalle.html', exp=exp)


@expedientes_bp.route('/armado/<int:id>/ver')
@login_required
def armado_ver(id):
    exp = db.get_or_404(Expediente, id)
    return send_file(BytesIO(exp.datos or b''), mimetype='application/pdf',
                     as_attachment=bool(request.args.get('descargar')),
                     download_name=_nombre_descarga(exp.codigo, exp.nombre,
                                                    exp.numero_lote), max_age=0)


@expedientes_bp.route('/armado/<int:id>/regenerar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def armado_regenerar(id):
    exp = db.get_or_404(Expediente, id)
    if not exp.plantilla:
        flash('No se puede regenerar: la plantilla original ya no existe.', 'warning')
        return redirect(url_for('expedientes.armado_detalle', id=id))
    contexto = {'lote': exp.numero_lote, 'producto': exp.producto, 'codigo': exp.codigo,
                'fecha': (exp.fecha_expediente or date.today()).strftime('%d/%m/%Y'),
                'version': exp.plantilla.version}
    buf, n = svc.ensamblar(exp.plantilla, contexto)
    if n == 0:
        flash('La plantilla ya no tiene páginas; el expediente no se regeneró.',
              'warning')
        return redirect(url_for('expedientes.armado_detalle', id=id))
    data = buf.getvalue()
    exp.datos = data
    exp.num_paginas = n
    exp.tamano_bytes = len(data)
    exp.fecha_generacion = datetime.utcnow()
    db.session.commit()
    registrar_log('GENERACION', 'Expedientes',
                  f'Expediente «{exp.nombre}» regenerado con versiones vigentes')
    flash(f'Expediente regenerado con las versiones vigentes ({n} páginas).', 'success')
    return redirect(url_for('expedientes.armado_detalle', id=id))


@expedientes_bp.route('/armado/<int:id>/eliminar', methods=['POST'])
@login_required
@rol_requerido('gestor_doc')
def armado_eliminar(id):
    exp = db.get_or_404(Expediente, id)
    nombre = exp.nombre
    db.session.delete(exp)
    db.session.commit()
    registrar_log('BAJA', 'Expedientes', f'Expediente «{nombre}» eliminado')
    flash('Expediente eliminado.', 'success')
    return redirect(url_for('expedientes.armados'))
