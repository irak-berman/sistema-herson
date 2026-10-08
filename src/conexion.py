# -*- coding: utf-8 -*-
"""
Conexión a la base de datos del sistema de inventario.

Centraliza la apertura de la base para que el resto del código no
necesite conocer su ruta ni acordarse de activar las llaves foráneas,
que en SQLite vienen desactivadas por omisión.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# La ruta se calcula a partir de la ubicación de este archivo, no del
# directorio desde donde se ejecute el programa. Así funciona igual si
# se lanza desde la terminal, desde VS Code o desde un acceso directo.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_BASE = RAIZ_PROYECTO / 'basedatos' / 'herson.db'


class BaseNoEncontrada(Exception):
    """Se lanza cuando el archivo de la base de datos no existe."""


def abrir_conexion(ruta: Path = RUTA_BASE) -> sqlite3.Connection:
    """
    Abre una conexión a la base de datos y la deja lista para usarse.

    Aplica tres ajustes que el resto del código da por hechos.
    Las llaves foráneas quedan activas, de modo que las relaciones del
    modelo se validen de verdad. Las filas se devuelven como objetos
    accesibles por nombre de columna, lo que evita depender del orden de
    los campos. Y el modo WAL permite leer mientras se escribe, que es
    lo que mantiene fluida la interfaz.
    """
    if not ruta.exists():
        raise BaseNoEncontrada(
            f'No se encontró la base de datos en {ruta}. '
            f'Ejecute primero basedatos/crear_base.py'
        )

    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    conexion.execute('PRAGMA foreign_keys = ON')
    conexion.execute('PRAGMA journal_mode = WAL')
    return conexion


@contextmanager
def conexion_abierta(ruta: Path = RUTA_BASE):
    """
    Entrega una conexión y se encarga de cerrarla al terminar.

    Confirma los cambios si el bloque concluye sin errores y los
    deshace si ocurre una excepción, de modo que una venta a medio
    registrar nunca quede guardada en la base.

    Uso:
        with conexion_abierta() as conexion:
            conexion.execute(...)
    """
    conexion = abrir_conexion(ruta)
    try:
        yield conexion
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def consultar(sentencia: str, parametros: tuple = ()) -> list:
    """Ejecuta una consulta de lectura y devuelve todas las filas."""
    with conexion_abierta() as conexion:
        return conexion.execute(sentencia, parametros).fetchall()


def consultar_una(sentencia: str, parametros: tuple = ()):
    """Ejecuta una consulta de lectura y devuelve la primera fila o None."""
    with conexion_abierta() as conexion:
        return conexion.execute(sentencia, parametros).fetchone()


def ejecutar(sentencia: str, parametros: tuple = ()) -> int:
    """
    Ejecuta una sentencia de escritura y devuelve el identificador
    del renglón insertado.
    """
    with conexion_abierta() as conexion:
        cursor = conexion.execute(sentencia, parametros)
        return cursor.lastrowid


if __name__ == '__main__':
    # Comprobación rápida de que la conexión funciona
    try:
        with conexion_abierta() as con:
            version = con.execute('SELECT sqlite_version()').fetchone()[0]
            tablas = con.execute("""
                SELECT COUNT(*) FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """).fetchone()[0]
            llaves = con.execute('PRAGMA foreign_keys').fetchone()[0]

        print(f'Base de datos  : {RUTA_BASE.name}')
        print(f'SQLite         : {version}')
        print(f'Tablas         : {tablas}')
        print(f'Llaves foráneas: {"activas" if llaves else "inactivas"}')
    except BaseNoEncontrada as error:
        print(f'Error: {error}')
