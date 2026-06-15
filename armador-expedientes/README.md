# Armador de Expedientes (Batch Records)

Aplicación **independiente** y **100 % local** para armar expedientes / batch
records de fórmulas maestras farmacéuticas en PDF.

No tiene relación con ningún otro sistema. **No requiere instalación ni permisos
de administrador, ni Python, ni internet, ni servidor**: es una página que se
abre en el navegador y funciona sola.

## Cómo se usa

1. Abra el archivo **`index.html`** con doble clic (en Windows también puede usar
   **`abrir.bat`**). Se abre en su navegador (Chrome, Edge o Firefox).
2. Listo. Todo funciona dentro del navegador de su equipo.

> Los datos (PDF, configuraciones y expedientes) se guardan en el propio
> navegador de ese equipo. **No se envían a ningún lado.** Para respaldarlos o
> llevarlos a otra PC use **Datos / Respaldo → Exportar / Importar**.

## Qué hace

- **Registros / PDFs**: banco de PDF reutilizables (fórmulas maestras, registros,
  anexos…) con **historial de versiones**. Cuando un registro cambie, suba su
  nueva versión y quedará como la versión actual.
- **Plantillas (configuraciones)**: la estructura del expediente — qué registros
  van, en qué **orden**, qué **páginas** de cada uno y en qué **paso**. Se arma
  arrastrando los bloques (o con los botones ▲ ▼) y se reutiliza en cada lote.
- **Sellado y foliado**: foliado de hojas, encabezado por hoja y sello (p. ej.
  `ORIGINAL` / `COPIA CONTROLADA`) con marcadores `{producto}` `{lote}`
  `{codigo}` `{fecha}` `{pagina}` `{total}` `{version}`, más sello del paso por
  bloque. Las hojas salen listas para solo firmarlas/sellarlas a mano.
- **Generar y regenerar**: produce el PDF del expediente de un lote (descargar
  y/o guardar). Si un registro se actualiza, suba su nueva versión y
  **regenere**: el expediente toma las versiones vigentes.
- **Guardar como nueva configuración**: duplica una plantilla para crear
  variantes (otra presentación u otro producto).
- **Vista previa** del expediente en pantalla antes de generar.

## Flujo típico

`Registros / PDFs` → cargar los PDF → `Plantillas` → *Nueva plantilla* →
agregar y ordenar registros en el armador → `Generar expediente` (indicar lote)
→ descargar.

## Páginas (rangos)

Al insertar un registro puede elegir qué páginas usar:

- vacío = todas las páginas
- `1-3` = de la 1 a la 3
- `2,5,8` = páginas sueltas
- `4-` = de la 4 hasta el final

## Respaldo / mover a otra PC

En **Datos / Respaldo**:

- **Exportar respaldo**: descarga un archivo `.json` con todo (incluye los PDF).
- **Importar respaldo**: restaura desde ese `.json` (reemplaza lo actual).

## Notas técnicas

- Todo el armado de PDF ocurre en el navegador con
  [pdf-lib](https://pdf-lib.js.org/) (incluido en `vendor/`, funciona sin
  conexión).
- Almacenamiento local con IndexedDB.
- La carpeta `armador-expedientes/` es autónoma: puede copiarla a un USB, a una
  carpeta compartida o a su propio repositorio y seguirá funcionando.

## Estructura

```
armador-expedientes/
  index.html          Página principal
  abrir.bat           Lanzador para Windows (doble clic)
  css/estilos.css     Estilos
  js/motor-pdf.js     Motor de armado y sellado (pdf-lib)
  js/db.js            Almacenamiento local (IndexedDB)
  js/app.js           Interfaz y lógica
  vendor/pdf-lib.min.js   Librería de PDF (offline)
```
