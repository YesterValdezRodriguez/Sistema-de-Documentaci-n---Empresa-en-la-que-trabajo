"""Modelos del módulo de Armado de Expedientes (Batch Records / Fórmulas Maestras).

Conceptos:

* **ArchivoFuente**  — un PDF reutilizable (fórmula maestra, registro, anexo…)
  con historial de **versiones**. Cuando un registro se actualiza, se sube una
  versión nueva y se vuelve la versión actual.
* **PlantillaExpediente** — una *configuración* guardada: la estructura del
  expediente (qué archivos van, en qué orden, qué páginas, en qué paso) más las
  opciones de sellado/foliado.
* **ItemPlantilla** — cada bloque ordenado de una plantilla.
* **Expediente** — un expediente ya *armado* para un lote concreto; guarda el
  PDF final generado para trazabilidad y se puede regenerar con las versiones
  vigentes de cada registro.

Los PDF se guardan como BLOB dentro de la misma base SQLite para que la
aplicación sea 100 % portable (todo viaja en el archivo .db, sin carpetas ni
permisos especiales).
"""
from datetime import datetime
from app.extensions import db

TIPOS_ARCHIVO = ('MAESTRA', 'REGISTRO', 'ANEXO', 'OTRO')
TIPOS_ARCHIVO_NOMBRES = {
    'MAESTRA': 'Fórmula Maestra / Batch Record',
    'REGISTRO': 'Registro / Formato',
    'ANEXO': 'Anexo / Instructivo',
    'OTRO': 'Otro documento',
}

# Posiciones de sello sobre la hoja
POSICIONES = ('SUP_IZQ', 'SUP_CEN', 'SUP_DER', 'INF_IZQ', 'INF_CEN', 'INF_DER')
POSICIONES_NOMBRES = {
    'SUP_IZQ': 'Superior izquierda',
    'SUP_CEN': 'Superior centro',
    'SUP_DER': 'Superior derecha',
    'INF_IZQ': 'Inferior izquierda',
    'INF_CEN': 'Inferior centro',
    'INF_DER': 'Inferior derecha',
}


class ArchivoFuente(db.Model):
    """PDF reutilizable con historial de versiones."""
    __tablename__ = 'exp_archivos_fuente'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    codigo = db.Column(db.String(40), index=True)          # código FAFII u otro
    tipo = db.Column(db.String(20), default='REGISTRO', nullable=False, index=True)
    descripcion = db.Column(db.Text)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamentos.id'))
    version_actual_id = db.Column(db.Integer)              # apunta a VersionArchivo
    activo = db.Column(db.Boolean, default=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    departamento = db.relationship('Departamento')
    creado_por = db.relationship('Usuario')
    versiones = db.relationship(
        'VersionArchivo', backref='archivo',
        order_by='VersionArchivo.id.desc()',
        cascade='all, delete-orphan',
        foreign_keys='VersionArchivo.archivo_id')

    @property
    def tipo_nombre(self):
        return TIPOS_ARCHIVO_NOMBRES.get(self.tipo, self.tipo)

    @property
    def version_actual(self):
        """Versión marcada como actual; si no, la más reciente."""
        if self.version_actual_id:
            for v in self.versiones:
                if v.id == self.version_actual_id:
                    return v
        return self.versiones[0] if self.versiones else None

    @property
    def num_paginas(self):
        va = self.version_actual
        return va.num_paginas if va else 0

    @property
    def etiqueta_version(self):
        va = self.version_actual
        return va.numero_version if va else '—'

    def __repr__(self):
        return f'<ArchivoFuente {self.codigo or self.nombre}>'


class VersionArchivo(db.Model):
    """Una versión concreta (los bytes del PDF) de un archivo fuente."""
    __tablename__ = 'exp_versiones_archivo'

    id = db.Column(db.Integer, primary_key=True)
    archivo_id = db.Column(db.Integer, db.ForeignKey('exp_archivos_fuente.id'),
                           nullable=False, index=True)
    numero_version = db.Column(db.String(20), nullable=False)
    descripcion_cambio = db.Column(db.Text)
    nombre_original = db.Column(db.String(255))
    datos = db.Column(db.LargeBinary)                      # bytes del PDF
    num_paginas = db.Column(db.Integer, default=0)
    tamano_bytes = db.Column(db.Integer, default=0)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    creado_por = db.relationship('Usuario')

    @property
    def tamano_legible(self):
        return _tamano_legible(self.tamano_bytes)

    def __repr__(self):
        return f'<VersionArchivo {self.archivo_id} v{self.numero_version}>'


class PlantillaExpediente(db.Model):
    """Configuración guardada de un expediente (estructura + opciones de sello)."""
    __tablename__ = 'exp_plantillas'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    producto = db.Column(db.String(255))
    codigo = db.Column(db.String(60), index=True)
    version = db.Column(db.String(20), default='01')
    descripcion = db.Column(db.Text)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    # ---- Opciones de sellado / foliado (se aplican al generar) ----
    foliar = db.Column(db.Boolean, default=True, nullable=False)
    formato_folio = db.Column(db.String(120), default='Hoja {pagina} de {total}')
    posicion_folio = db.Column(db.String(10), default='INF_DER')

    mostrar_encabezado = db.Column(db.Boolean, default=False, nullable=False)
    formato_encabezado = db.Column(db.String(200), default='{producto}  |  Lote: {lote}')
    posicion_encabezado = db.Column(db.String(10), default='SUP_CEN')

    texto_sello = db.Column(db.String(120), default='')
    posicion_sello = db.Column(db.String(10), default='SUP_DER')

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow,
                                   onupdate=datetime.utcnow)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    creado_por = db.relationship('Usuario')
    items = db.relationship('ItemPlantilla', backref='plantilla',
                            order_by='ItemPlantilla.orden',
                            cascade='all, delete-orphan')

    @property
    def num_items(self):
        return len(self.items)

    @property
    def total_paginas(self):
        """Total de páginas estimadas según las versiones vigentes."""
        return sum(it.num_paginas for it in self.items)

    def __repr__(self):
        return f'<PlantillaExpediente {self.nombre}>'


class ItemPlantilla(db.Model):
    """Bloque ordenado dentro de una plantilla."""
    __tablename__ = 'exp_items_plantilla'

    id = db.Column(db.Integer, primary_key=True)
    plantilla_id = db.Column(db.Integer, db.ForeignKey('exp_plantillas.id'),
                             nullable=False, index=True)
    orden = db.Column(db.Integer, default=0, nullable=False)
    archivo_id = db.Column(db.Integer, db.ForeignKey('exp_archivos_fuente.id'),
                           nullable=False)
    usar_version_actual = db.Column(db.Boolean, default=True, nullable=False)
    version_fija_id = db.Column(db.Integer, db.ForeignKey('exp_versiones_archivo.id'))
    rango_paginas = db.Column(db.String(120), default='')   # '' = todas
    paso = db.Column(db.String(120))                         # etiqueta del paso
    titulo = db.Column(db.String(255))                       # descripción del bloque
    sellar_paso = db.Column(db.Boolean, default=False, nullable=False)

    archivo = db.relationship('ArchivoFuente')
    version_fija = db.relationship('VersionArchivo', foreign_keys=[version_fija_id])

    def version_efectiva(self):
        """Versión que realmente se usará al armar."""
        if not self.usar_version_actual and self.version_fija:
            return self.version_fija
        return self.archivo.version_actual if self.archivo else None

    @property
    def num_paginas(self):
        """Páginas que aporta este ítem según su rango y versión efectiva."""
        from app.services import expediente_service
        v = self.version_efectiva()
        if not v:
            return 0
        return len(expediente_service.parse_rango_paginas(
            self.rango_paginas, v.num_paginas or 0))

    @property
    def etiqueta_version(self):
        v = self.version_efectiva()
        if not v:
            return '—'
        return ('actual' if self.usar_version_actual else 'fija') + f' v{v.numero_version}'

    def __repr__(self):
        return f'<ItemPlantilla plantilla={self.plantilla_id} orden={self.orden}>'


class Expediente(db.Model):
    """Expediente (batch record) ya armado para un lote, con el PDF generado."""
    __tablename__ = 'exp_expedientes'

    id = db.Column(db.Integer, primary_key=True)
    plantilla_id = db.Column(db.Integer, db.ForeignKey('exp_plantillas.id'))
    nombre = db.Column(db.String(255), nullable=False)
    producto = db.Column(db.String(255))
    codigo = db.Column(db.String(60), index=True)
    numero_lote = db.Column(db.String(60), index=True)
    fecha_expediente = db.Column(db.Date)
    datos = db.Column(db.LargeBinary)
    num_paginas = db.Column(db.Integer, default=0)
    tamano_bytes = db.Column(db.Integer, default=0)
    fecha_generacion = db.Column(db.DateTime, default=datetime.utcnow)
    generado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    plantilla = db.relationship('PlantillaExpediente')
    generado_por = db.relationship('Usuario')

    @property
    def tamano_legible(self):
        return _tamano_legible(self.tamano_bytes)

    def __repr__(self):
        return f'<Expediente {self.codigo or self.nombre} lote={self.numero_lote}>'


def _tamano_legible(n):
    if not n:
        return '—'
    for unidad in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f'{n:.0f} {unidad}' if unidad == 'B' else f'{n:.1f} {unidad}'
        n /= 1024
    return f'{n:.1f} TB'
