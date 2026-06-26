# Generador de Certificados Kinnto

## Resumen

Construimos una herramienta local en Streamlit para generar certificados masivos o individuales a partir de una imagen base. La app permite subir el arte del certificado, cargar personas desde CSV o registrar una persona manualmente, ajustar el texto en una vista previa y generar archivos PNG, ZIP, CSV de resultados para Treble y links de Cloudinary.

La herramienta evoluciono desde un notebook de Colab con credenciales hardcodeadas hacia una interfaz usable, con configuracion local, guardado de historial y una identidad visual inspirada en Kinnto: fondo espacial oscuro, acentos neon, logo mascot tipo zorro/lobo espacial y un flujo mas cercano a un "Certificate Lab".

## Estado Actual

La app principal esta en:

```text
app.py
```

Se ejecuta localmente en:

```text
http://127.0.0.1:8501
```

Comando recomendado:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Tambien existen lanzadores:

```text
abrir_app.bat
start_app.ps1
```

## Funcionalidades Implementadas

- Carga de imagen base del certificado.
- Carga de CSV con personas.
- Plantilla CSV compatible con Treble: `country_code`, `cellphone`, `nombre`, `apellido`, `certificado`.
- Modo rapido para registrar una persona manualmente.
- Plantilla CSV descargable.
- Fuente opcional por carga manual.
- Fuente por defecto si existe en `assets/Figtree-Bold.ttf`.
- Seleccion de columnas para nombre, apellido, nombre completo y documento.
- Documento de identidad opcional.
- Vista previa del certificado antes de generar.
- Editor visual con mouse para ubicar nombre/documento sobre el certificado, manteniendo centrado horizontal.
- Movimiento vertical del texto con barra de pasos de 5 px y campo numerico de 1 en 1.
- Ajuste de tamano, tamano minimo, ancho maximo y color del nombre.
- Ajuste opcional del documento dentro de un panel desplegable.
- Generacion masiva de certificados PNG.
- Descarga ZIP con certificados.
- CSV final compatible con Treble, escribiendo el enlace en la columna `certificado`.
- Subida opcional a Cloudinary usando llaves locales.
- Guardado local de generaciones en `certificados_guardados/`.
- Descarga de lotes recientes desde la barra lateral.
- Guardado y carga de presets de diseno en `presets/`.
- Diseno visual oscuro/espacial con acentos Kinnto.
- Logo mascot guardado como asset local.

## Archivos y Carpetas Importantes

```text
app.py
```

Aplicacion principal de Streamlit. Contiene la interfaz, generacion de certificados, lectura de CSV, subida a Cloudinary y guardado local.

```text
requirements.txt
```

Dependencias principales: Streamlit, pandas, Pillow y Cloudinary.

```text
.streamlit/config.toml
```

Configuracion local de Streamlit para correr en `127.0.0.1:8501` y evitar el onboarding de email.

```text
.streamlit/secrets.toml
```

Archivo local para llaves de Cloudinary. No debe subirse a Git.

```text
assets/brand/
```

Assets visuales del mascot Kinnto. Incluye la version limpia:

```text
assets/brand/kinnto-space-wolf-clean.png
```

```text
certificados_guardados/
```

Historial local de lotes generados. Esta carpeta se ignora en Git.

```text
presets/
```

Presets locales de diseno en JSON. Guardan posicion, tamano, color, ancho, centrado, prefijo del documento y carpeta de Cloudinary.

```text
README.md
```

Instrucciones rapidas de uso.

## Cloudinary

La app ya no pide las llaves en pantalla. Las lee desde:

```text
.streamlit/secrets.toml
```

Esto permite que el usuario solo suba archivos y genere certificados sin repetir credenciales.

Importante: las llaves usadas originalmente fueron compartidas en texto. Lo ideal es rotarlas en Cloudinary y actualizar el archivo local.

## Flujo de Uso

1. Abrir la app con Streamlit.
2. Subir el arte base del certificado.
3. Elegir si se cargaran personas por CSV o una persona manual.
4. Si se usa CSV, descargar plantilla si hace falta.
5. Seleccionar columnas de nombre y documento si se necesita ajustar algo distinto a `nombre` + `apellido`.
6. Ajustar altura, tamano, ancho y color del nombre.
7. Abrir el panel de documento solo si se requiere mostrarlo.
8. Guardar o aplicar un preset si se quiere reutilizar el ajuste.
9. Revisar la vista previa orbital.
10. Generar certificados.
11. Descargar ZIP/CSV de Treble o usar los links de Cloudinary.
12. Recuperar lotes anteriores desde la barra lateral.

## Decisiones de Diseno

- Se priorizo usabilidad sobre configuracion tecnica.
- Cloudinary queda configurado una sola vez y oculto del flujo principal.
- El documento se mantiene opcional para no cargar la pantalla.
- Los controles de texto combinan una barra suave para mover rapido y campos numericos de paso 1 para ajuste fino.
- El diseño visual se movio hacia una estetica espacial/neon, usando el mascot como senal de marca.
- El historial local permite hacer certificados rapidos sin perder generaciones anteriores.
- El editor visual queda como componente local de Streamlit, sin depender de servicios externos.

## Limitaciones Actuales

- El editor visual mueve el texto por clic o arrastre vertical, pero no reemplaza un editor tipo Canva con guias avanzadas.
- Las posiciones no se guardan por plantilla de certificado.
- La fuente Figtree no quedo descargada automaticamente por bloqueo TLS local; la app esta lista para usarla si se coloca manualmente.
- No hay login ni empaquetado como app instalable.
- El preview depende de Streamlit; para edicion tipo Canva se necesitaria un componente frontend mas avanzado.

## Siguientes Pasos Recomendados

1. Pulir editor visual con mouse.
   - Agregar guias de alineacion vertical.
   - Mostrar limites reales del texto ajustado.
   - Mantener controles numericos como ajuste fino.

2. Crear biblioteca de plantillas.
   - Subir varios artes base.
   - Elegir plantilla desde la app.
   - Recordar el ultimo ajuste usado para cada plantilla.

3. Mejorar gestion de historial.
   - Buscar por nombre.
   - Re-generar un certificado anterior.
   - Copiar link de Cloudinary.
   - Descargar un solo certificado, no siempre el lote completo.

4. Empaquetar como herramienta de escritorio.
   - Acceso con doble clic.
   - Icono Kinnto.
   - Sin terminal visible para usuarios finales.

5. Validar CSV antes de generar.
   - Detectar columnas faltantes.
   - Mostrar filas vacias.
   - Avisar nombres duplicados.
   - Prevenir sobreescritura en Cloudinary.

6. Mejorar salida final.
   - Generar PDF opcional.
   - Generar PNG y PDF por persona.
   - Agregar QR al certificado si se requiere.

7. Seguridad.
   - Rotar llaves Cloudinary.
   - Mantener `.streamlit/secrets.toml` fuera de Git.
   - Crear un `.streamlit/secrets.example.toml` sin valores reales.

## Ideas Extra

- Modo "certificado express": solo nombre, generar y copiar link.
- Boton "duplicar ultimo ajuste" para nuevos certificados.
- Estado de subida con contador: generados, subidos, fallidos.
- Marca de agua opcional para previews.
- Selector de logo/mascot para exportaciones internas.
- Paletas predefinidas: Kinnto Neon, Blanco Formal, Dorado Premium.
- Control de texto con sombra o borde para mejorar legibilidad sobre fondos complejos.

## Nota Final

La herramienta ya cumple el flujo base y esta en una buena etapa para convertirse en producto interno. El siguiente gran salto no es mas generacion, sino mejor experiencia: presets, arrastre visual, historial inteligente y empaquetado para uso diario sin friccion.
