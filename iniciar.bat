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
REM Autor: Irak Berman Gutierrez
REM Estadia profesional, Ingenieria en Sistemas Computacionales, UVEG
REM ---------------------------------------------------------------

cd /d "%~dp0"

set DIRECCION=http://localhost:8501

REM El entorno virtual del proyecto
if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual en .venv
    echo Ejecute primero: python -m venv .venv
    pause
    exit /b 1
)

echo Iniciando el sistema...

REM El servidor corre en segundo plano, en una ventana minimizada
start "Servidor HERSON" /min ".venv\Scripts\python.exe" -m streamlit run src\app.py

REM Se le da tiempo al servidor para quedar disponible
timeout /t 4 /nobreak >nul

REM Se busca un navegador basado en Chromium para abrirlo en modo
REM aplicacion. Edge viene incluido en Windows, asi que siempre hay uno.
set NAVEGADOR=
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "NAVEGADOR=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "NAVEGADOR=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    set "NAVEGADOR=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    set "NAVEGADOR=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
)

if defined NAVEGADOR (
    start "" "%NAVEGADOR%" --app=%DIRECCION% --new-window
) else (
    REM Sin navegador basado en Chromium, se abre el predeterminado
    start "" %DIRECCION%
)

exit
