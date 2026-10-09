@echo off
chcp 65001 >nul
title Detener el sistema HERSON

REM ---------------------------------------------------------------
REM Detiene el servidor del sistema de inventario.
REM
REM Cerrar la ventana de la aplicacion no detiene el servidor, porque
REM corre en segundo plano. Este archivo lo cierra.
REM ---------------------------------------------------------------

echo Deteniendo el servidor...
taskkill /FI "WINDOWTITLE eq Servidor HERSON*" /T /F >nul 2>&1
echo Listo.
timeout /t 2 /nobreak >nul
exit
