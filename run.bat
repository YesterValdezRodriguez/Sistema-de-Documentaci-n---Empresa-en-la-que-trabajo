@echo off
REM =====================================================
REM  QMS FARACH - Lanzador para Windows
REM =====================================================
cd /d "%~dp0"

IF EXIST venv\Scripts\activate.bat (
    echo Activando entorno virtual...
    call venv\Scripts\activate.bat
) ELSE (
    echo No existe entorno virtual. Creando venv...
    python -m venv venv
    call venv\Scripts\activate.bat
)

echo Instalando dependencias...
pip install -r requirements.txt --quiet

echo Iniciando QMS FARACH en http://127.0.0.1:5000 ...
start "" http://127.0.0.1:5000
python app.py

pause
