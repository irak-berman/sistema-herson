@echo off
chcp 65001 >nul
title Deposito Dental HERSON

REM ---------------------------------------------------------------
REM Lanzador del sistema de control de inventario.
REM
REM Arranca el servidor local y abre la aplicacion en una ventana sin
REM barra de direcciones ni pestanas, de modo que se comporte como un
REM programa de escritorio y no como una pagina web.
REM
REM La opcion headless se pasa aqui y no en .streamlit\config.toml.
REM Puesta en la configuracion general aplicaria tambien al arrancar
REM desde la terminal, y entonces no abriria ningun navegador. Aqui si
REM se necesita, porque de lo contrario Streamlit abriria una pestana
REM normal ademas de la ventana de aplicacion.
REM
REM Autor: Irak Berman Gutierrez
REM Estadia profesional, Ingenieria en Sistemas Computacionales, UVEG
REM ---------------------------------------------------------------

cd /d "%~dp0"

set PUERTO=8501
set DIRECCION=http://localhost:%PUERTO%

REM El entorno virtual del proyecto
if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual en .venv
    echo Ejecute primero: python -m venv .venv
    pause
    exit /b 1
)

echo Iniciando el sistema...

REM El servidor corre en segundo plano, en una ventana minimizada
start "Servidor HERSON" /min ".venv\Scripts\python.exe" -m streamlit run src\app.py --server.port %PUERTO% --server.headless true

REM Se espera a que el servidor acepte conexiones. Una espera fija se
REM queda corta el primer arranque del dia, cuando Windows todavia no
REM tiene en memoria las bibliotecas, y el navegador abre sobre un
REM error de conexion.
set INTENTOS=0

:esperar
set /a INTENTOS+=1
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('localhost', %PUERTO%); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto abrir
if %INTENTOS% lss 60 goto esperar

echo.
echo No se pudo iniciar el sistema.
echo Revise que las dependencias esten instaladas con:
echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1

:abrir
REM Se busca un navegador basado en Chromium para abrirlo en modo
REM aplicacion. Edge viene incluido en Windows, asi que siempre hay uno.
set NAVEGADOR=
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "NAVEGADOR=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "NAVEGADOR=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set "NAVEGADOR=%LocalAppData%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    set "NAVEGADOR=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    set "NAVEGADOR=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
)

if defined NAVEGADOR (
    start "" "%NAVEGADOR%" --app=%DIRECCION% --window-size=1440,900 --new-window
) else (
    REM Sin navegador basado en Chromium, se abre el predeterminado
    start "" %DIRECCION%
)

exit
