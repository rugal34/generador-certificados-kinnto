# Montaje en produccion

## Opcion recomendada: Streamlit Community Cloud

1. Sube este proyecto a un repositorio privado en GitHub.
2. Verifica que `.streamlit/secrets.toml` no se suba. Ya esta en `.gitignore`.
3. En Streamlit Community Cloud, crea una app nueva desde el repo.
4. Configura:

```text
Main file path: app.py
Python dependencies: requirements.txt
```

5. En el panel de secretos de Streamlit pega el contenido de `.streamlit/secrets.example.toml` usando las llaves reales de Cloudinary.
6. Despliega y prueba con un CSV Treble de ejemplo:

```text
country_code,cellphone,nombre,certificado
57,3001234567,Ana Martinez,
```

## Importante para produccion

- Rota las llaves actuales de Cloudinary antes de publicar.
- Usa un repositorio privado.
- No subas `.streamlit/secrets.toml`.
- Los certificados generados se descargan al momento. El historial local (`certificados_guardados/`) no debe asumirse persistente en hosting cloud.
- Los presets JSON incluidos en el repo si quedan disponibles en la app publicada.

## Alternativa con servidor propio

Si se monta en una VM o servicio tipo Render/Railway, el comando base es:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true
```

En ese caso configura las variables de entorno equivalentes:

```text
CLOUDINARY_CLOUD_NAME
CLOUDINARY_API_KEY
CLOUDINARY_API_SECRET
CLOUDINARY_FOLDER
```
