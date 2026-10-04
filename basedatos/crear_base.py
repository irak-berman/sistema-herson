# -*- coding: utf-8 -*-
"""
Crea la base de datos del sistema de control de inventario de
Depósito Dental HERSON a partir del script esquema.sql.

El archivo .db no se versiona: se reconstruye ejecutando este script,
de modo que el esquema sea siempre la única fuente de verdad.

Uso desde la terminal, estando en la carpeta del proyecto:
    python basedatos/crear_base.py

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import sqlite3
import sys
from pathlib import Path

# Rutas relativas al archivo, para que funcione sin importar desde
# qué carpeta se ejecute el script
CARPETA = Path(__file__).resolve().parent
RUTA_ESQUEMA = CARPETA / 'esquema.sql'
RUTA_BASE = CARPETA / 'herson.db'


def leer_esquema(ruta: Path) -> str:
    """Devuelve el contenido del script SQL."""
    if not ruta.exists():
        raise FileNotFoundError(f'No se encontró el script: {ruta}')
    return ruta.read_text(encoding='utf-8')


def crear_base(ruta_base: Path, sentencias: str) -> None:
    """Crea la base de datos y ejecuta el script de creación."""
    # Si ya existe, se elimina para partir siempre de un estado limpio
    if ruta_base.exists():
        ruta_base.unlink()
        print(f'Base anterior eliminada: {ruta_base.name}')

    conexion = sqlite3.connect(ruta_base)
    try:
        conexion.executescript(sentencias)
        conexion.commit()
        print(f'Base de datos creada: {ruta_base.name}')
    finally:
        conexion.close()


def verificar(ruta_base: Path) -> None:
    """Lista los objetos creados y confirma las llaves foráneas."""
    conexion = sqlite3.connect(ruta_base)
    try:
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT type, name
            FROM sqlite_master
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
        """)
        objetos = cursor.fetchall()

        tablas = [n for t, n in objetos if t == 'table']
        vistas = [n for t, n in objetos if t == 'view']

        print(f'\nTablas creadas ({len(tablas)}):')
        for nombre in tablas:
            print(f'  - {nombre}')

        print(f'\nVistas creadas ({len(vistas)}):')
        for nombre in vistas:
            print(f'  - {nombre}')

        # Comprobación de integridad del archivo
        cursor.execute('PRAGMA integrity_check')
        print(f'\nIntegridad: {cursor.fetchone()[0]}')
    finally:
        conexion.close()


def main() -> int:
    try:
        sentencias = leer_esquema(RUTA_ESQUEMA)
        crear_base(RUTA_BASE, sentencias)
        verificar(RUTA_BASE)
        return 0
    except (FileNotFoundError, sqlite3.Error) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())