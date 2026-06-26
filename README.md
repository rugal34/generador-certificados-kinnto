# Generador de certificados Kinnto

Herramienta local para crear certificados masivos desde una imagen base y un CSV listo para Treble.

## Iniciar

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Flujo

1. Carga la imagen base del certificado.
2. Carga el CSV con `country_code`, `cellphone`, `nombre`, `apellido` y `certificado`, o registra una persona manualmente.
3. Carga una fuente `.ttf` u `.otf` solo si quieres reemplazar la fuente por defecto.
4. La app usa `nombre` + `apellido` por defecto.
5. Activa el documento si el CSV trae esa columna.
6. Ajusta la altura con el editor de mouse, la barra suave o el campo fino de 1 en 1.
7. Guarda un preset si quieres reutilizar ese mismo diseno despues.
8. Genera el ZIP y el CSV de resultados para subirlo a Treble.

## CSV para Treble

La plantilla descargable usa estas columnas:

```text
country_code,cellphone,nombre,apellido,certificado
```

Al generar, la app devuelve un CSV con esas mismas columnas y escribe el link de Cloudinary en `certificado`.

## Editor visual

En la vista previa puedes activar `Editar con mouse` para mover el nombre o el documento directamente sobre el certificado. El texto se mantiene centrado de izquierda a derecha; el mouse solo ajusta la altura. Los controles numericos siguen disponibles para el ajuste fino.

## Fuente por defecto

Para que la fuente salga siempre sin subirla cada vez, pon el archivo en:

```text
assets/Figtree-Bold.ttf
```

La app tambien reconoce `assets/Figtree-Bold (1).ttf`.

## Guardados

Cada generacion puede guardarse en `certificados_guardados/`. Desde la barra lateral puedes descargar de nuevo los ultimos lotes creados.

## Presets

Los ajustes de diseno se guardan en `presets/` como archivos JSON locales.

Un preset conserva posicion, tamano, ancho, color, centrado, prefijo del documento y carpeta de Cloudinary.

## Cloudinary

La app lee las llaves desde `.streamlit/secrets.toml`, asi no tienes que pegarlas en pantalla cada vez.

Ese archivo esta ignorado por Git para evitar subir credenciales por accidente.

## Produccion

La guia de montaje esta en `DEPLOY.md`.

Ruta recomendada:

1. Subir el proyecto a un repo privado en GitHub.
2. Crear la app en Streamlit Community Cloud apuntando a `app.py`.
3. Pegar las llaves reales en el panel de secretos usando `.streamlit/secrets.example.toml` como plantilla.
4. Probar con un CSV Treble y descargar el CSV final con la columna `certificado`.
