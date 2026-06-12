# QMS FARACH — Sistema de Gestión de Calidad Documental

Aplicación web portable para la gestión de calidad documental de
**Laboratorios Alfa II (FARACH, S.A.)**, bajo estándares GMP/BPF y el sistema
de clasificación documental **FAFII**.

Corre 100% local con SQLite, sin conexión a internet ni servicios externos.

## Requisitos

- Python 3.10 o superior

## Instalación y ejecución

### Windows

Doble clic en `run.bat` (crea el venv, instala dependencias y abre el navegador).

### Manual (cualquier sistema)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abrir <http://127.0.0.1:5000>. La base de datos `qms_farach.db` y los datos
iniciales (departamentos, tipos de documento, usuarios) se crean
automáticamente en el primer arranque.

## Usuarios iniciales

| Usuario   | Contraseña   | Rol               |
|-----------|--------------|-------------------|
| `admin`   | `farach2025` | Administrador     |
| `gestor1` | `demo123`    | Gestor Documental |

> Cambie las contraseñas después del primer ingreso.

## Módulos

1. **Documentos** — Lista maestra FAFII (POE, FOR, INS/IT, LG, POI, PRO, REG),
   ciclo de vida Borrador → En Revisión → Aprobado → Vigente → Obsoleto,
   versiones, copias controladas, alertas de vencimiento, PDF y Excel.
2. **Control de Cambios** — Solicitudes SC-AAAA-NNN con evaluación,
   implementación, cierre formal y comentarios.
3. **Capacitaciones** — Planes por cargo, sesiones con asistencia y
   calificaciones, registros de entrenamiento/disclosure, PDFs de asistencia.
4. **CAPA** — CAPA-AAAA-NNN con análisis de causa raíz, acciones específicas,
   verificación de efectividad y alertas de vencimiento.
5. **Auditorías** — AUD-AAAA-NNN con hallazgos, generación automática de CAPA
   por hallazgo e informe PDF.
6. **Dashboard** — Indicadores, gráficos (Chart.js) y alertas en tiempo real.
7. **Administración** — Usuarios y roles, catálogos, log de auditoría del
   sistema y backup de la base de datos.

## Roles

| Acción            | admin | gestor_doc | aprobador | usuario_lectura |
|-------------------|:-----:|:----------:|:---------:|:---------------:|
| Ver documentos    |  ✓    |     ✓      |     ✓     |        ✓        |
| Crear/editar docs |  ✓    |     ✓      |     –     |        –        |
| Aprobar docs      |  ✓    |     –      |     ✓     |        –        |
| CAPA / Cambios    |  ✓    |     ✓      |     ✓     |        –        |
| Administración    |  ✓    |     –      |     –     |        –        |

## Stack

Flask · SQLAlchemy · SQLite · Flask-Login · Flask-WTF (CSRF) · Flask-Migrate ·
Bootstrap 5 · Chart.js · ReportLab · openpyxl

## Migraciones de esquema

```bash
flask db init      # solo la primera vez
flask db migrate -m "descripción del cambio"
flask db upgrade
```
