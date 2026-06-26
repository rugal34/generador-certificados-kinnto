@echo off
cd /d "%~dp0"
echo Abriendo generador de certificados Kinnto...
echo.
echo Deja esta ventana abierta mientras uses la app.
echo Si aparece "You can now view your Streamlit app", entra a:
echo http://localhost:8501
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_app.ps1"
pause
