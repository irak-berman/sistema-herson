# -*- coding: utf-8 -*-
"""
Respaldo y restauración de la base de datos del Depósito Dental HERSON.

Por qué este script y no copiar el archivo con el explorador.

La base opera en modo WAL, lo que significa que las escrituras recientes
pueden estar todavía en el archivo herson.db-wal y no dentro de
herson.db. Copiar el archivo con el explorador mientras el sistema está
abierto puede producir una copia incompleta sin que nada lo advierta, y
eso se descubre el día que se necesita. La función backup() de sqlite3
abre la base como lo haría el propio motor y entrega una copia
consistente aunque haya alguien usando el sistema en ese momento.

Uso desde la carpeta del proyecto, con el entorno activado.

    python basedatos/respaldo.py              crea un respaldo
    python basedatos/respaldo.py --probar     crea uno y prueba restaurarlo
    python basedatos/respaldo.py --listar     muestra los respaldos que hay

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------
# Rutas y política de conservación
#
# Se calculan a partir de la ubicación de este archivo y no del
# directorio desde el que se invoque, para que el respaldo caiga siempre
# en el mismo lugar sin importar desde dónde se ejecute.
# ---------------------------------------------------------------------
CARPETA_BASE = Path(__file__).resolve().parent
RUTA_BASE = CARPETA_BASE / 'herson.db'
CARPETA_RESPALDOS = CARPETA_BASE / 'respaldos'

# Cuántas copias conservar. Con una copia diaria esto cubre un mes, que
# es tiempo suficiente para notar un borrado y volver atrás.
COPIAS_A_CONSERVAR = 30

PREFIJO = 'herson_'
SUFIJO = '.db'


def nombre_de_respaldo(momento: datetime | None = None) -> str:
    """Nombre ordenable cronológicamente al listar la carpeta."""
    momento = momento or datetime.now()
    return f'{PREFIJO}{momento:%Y%m%d_%H%M%S}{SUFIJO}'


def respaldos_existentes() -> list[Path]:
    """Los respaldos que hay, del más reciente al más antiguo."""
    if not CARPETA_RESPALDOS.exists():
        return []
    copias = CARPETA_RESPALDOS.glob(f'{PREFIJO}*{SUFIJO}')
    return sorted(copias, key=lambda p: p.name, reverse=True)


def verificar(ruta: Path) -> None:
    """
    Comprueba la integridad de una base.

    Se ejecuta sobre la copia recién creada. Un respaldo que no se
    verifica es una suposición, y la suposición se descubre falsa
    justo el día que hace falta.
    """
    with sqlite3.connect(f'file:{ruta}?mode=ro', uri=True) as cnx:
        resultado = cnx.execute('PRAGMA integrity_check').fetchone()[0]
        if resultado != 'ok':
            raise RuntimeError(
                f'La copia {ruta.name} no pasó la comprobación de '
                f'integridad: {resultado}')


def contar_renglones(ruta: Path) -> dict[str, int]:
    """
    Cuenta los renglones de las tablas con información del negocio.

    Sirve para comparar el original contra la copia. La comprobación de
    integridad dice que el archivo no está corrupto, pero no dice que
    tenga los mismos datos.
    """
    tablas = ('producto', 'presentacion', 'lote', 'movimiento',
              'venta', 'venta_detalle', 'precio_historial')
    conteo = {}
    with sqlite3.connect(f'file:{ruta}?mode=ro', uri=True) as cnx:
        presentes = {f[0] for f in cnx.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        for tabla in tablas:
            if tabla in presentes:
                conteo[tabla] = cnx.execute(
                    f'SELECT COUNT(*) FROM {tabla}').fetchone()[0]
    return conteo


def podar() -> list[Path]:
    """Elimina las copias que sobran de las más antiguas."""
    sobrantes = respaldos_existentes()[COPIAS_A_CONSERVAR:]
    for copia in sobrantes:
        copia.unlink()
    return sobrantes


def respaldar(verbose: bool = True) -> Path:
    """
    Crea una copia consistente de la base y la verifica.

    Devuelve la ruta de la copia creada.
    """
    if not RUTA_BASE.exists():
        raise FileNotFoundError(f'No existe la base en {RUTA_BASE}')

    CARPETA_RESPALDOS.mkdir(parents=True, exist_ok=True)
    destino = CARPETA_RESPALDOS / nombre_de_respaldo()

    # La copia se escribe primero con un nombre temporal y se renombra
    # al final. Si el proceso se interrumpe a la mitad, en la carpeta
    # queda un archivo .parcial y no un respaldo incompleto que parezca
    # bueno.
    parcial = destino.with_suffix('.parcial')

    origen = sqlite3.connect(f'file:{RUTA_BASE}?mode=ro', uri=True)
    try:
        copia = sqlite3.connect(parcial)
        try:
            # Aquí está lo importante. backup() lee la base a través del
            # motor, de modo que el contenido del WAL queda incluido.
            origen.backup(copia)
        finally:
            copia.close()
    finally:
        origen.close()

    verificar(parcial)
    parcial.rename(destino)

    if verbose:
        tamano = destino.stat().st_size / 1024
        print(f'Respaldo creado: {destino.name} ({tamano:,.0f} KB)')

        original = contar_renglones(RUTA_BASE)
        respaldo = contar_renglones(destino)
        if original == respaldo:
            total = sum(original.values())
            print(f'Contenido verificado: {total:,} renglones en '
                  f'{len(original)} tablas, iguales al original.')
        else:
            # No se interrumpe, porque la copia ya existe y es mejor
            # tenerla que no tenerla, pero sí se advierte.
            print('AVISO: el conteo de renglones no coincide con el '
                  'original. Probablemente alguien escribió en la base '
                  'durante el respaldo.')
            for tabla in sorted(set(original) | set(respaldo)):
                a, b = original.get(tabla, 0), respaldo.get(tabla, 0)
                if a != b:
                    print(f'  {tabla}: original {a}, copia {b}')

        eliminadas = podar()
        if eliminadas:
            print(f'Se eliminaron {len(eliminadas)} copias antiguas, '
                  f'se conservan las {COPIAS_A_CONSERVAR} más recientes.')

    return destino


def probar_restauracion(copia: Path) -> None:
    """
    Restaura la copia en una ubicación temporal y la revisa.

    No toca la base real. El objetivo es comprobar que la copia sirve
    para volver a operar, no solo que el archivo existe.
    """
    with tempfile.TemporaryDirectory() as temporal:
        restaurada = Path(temporal) / 'restaurada.db'

        origen = sqlite3.connect(f'file:{copia}?mode=ro', uri=True)
        try:
            destino = sqlite3.connect(restaurada)
            try:
                origen.backup(destino)
            finally:
                destino.close()
        finally:
            origen.close()

        verificar(restaurada)

        # Se comprueba que los objetos del esquema estén completos, no
        # solo que el archivo abra.
        with sqlite3.connect(f'file:{restaurada}?mode=ro', uri=True) as cnx:
            objetos = cnx.execute(
                "SELECT type, COUNT(*) FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' GROUP BY type").fetchall()
        resumen = ', '.join(f'{cantidad} {tipo}' for tipo, cantidad in objetos)

        conteo = contar_renglones(restaurada)
        print(f'Restauración probada desde {copia.name}')
        print(f'  Objetos del esquema: {resumen}')
        print(f'  Renglones: {sum(conteo.values()):,} en '
              f'{len(conteo)} tablas')
        print('  La copia sirve para volver a operar.')


def restaurar_de_verdad(copia: Path) -> None:
    """
    Sustituye la base real por una copia. Operación destructiva.

    Antes de sobrescribir se respalda la base actual, porque restaurar
    por equivocación es tan fácil como perder los datos.
    """
    if not copia.exists():
        raise FileNotFoundError(f'No existe la copia {copia}')
    verificar(copia)

    if RUTA_BASE.exists():
        previo = respaldar(verbose=False)
        print(f'La base actual se respaldó antes de sustituirla: '
              f'{previo.name}')

    # Los archivos auxiliares del modo WAL deben irse junto con la base
    # vieja. Si se quedan, el motor intenta aplicarlos sobre la base
    # restaurada y el resultado es impredecible.
    for auxiliar in ('-wal', '-shm'):
        companero = RUTA_BASE.with_name(RUTA_BASE.name + auxiliar)
        if companero.exists():
            companero.unlink()

    origen = sqlite3.connect(f'file:{copia}?mode=ro', uri=True)
    try:
        destino = sqlite3.connect(RUTA_BASE)
        try:
            origen.backup(destino)
        finally:
            destino.close()
    finally:
        origen.close()

    verificar(RUTA_BASE)
    print(f'Base restaurada desde {copia.name}')


def listar() -> None:
    """Muestra los respaldos disponibles."""
    copias = respaldos_existentes()
    if not copias:
        print('No hay respaldos todavía.')
        return
    print(f'{len(copias)} respaldos, del más reciente al más antiguo.')
    for copia in copias:
        momento = datetime.strptime(
            copia.stem[len(PREFIJO):], '%Y%m%d_%H%M%S')
        tamano = copia.stat().st_size / 1024
        print(f'  {copia.name}   {momento:%d/%m/%Y %H:%M}   '
              f'{tamano:,.0f} KB')


def main() -> int:
    analizador = argparse.ArgumentParser(
        description='Respaldo de la base de datos del Depósito Dental '
                    'HERSON.')
    analizador.add_argument('--probar', action='store_true',
                            help='crea un respaldo y prueba restaurarlo')
    analizador.add_argument('--listar', action='store_true',
                            help='muestra los respaldos existentes')
    analizador.add_argument('--restaurar', metavar='ARCHIVO',
                            help='sustituye la base por esta copia')
    argumentos = analizador.parse_args()

    try:
        if argumentos.listar:
            listar()
        elif argumentos.restaurar:
            ruta = Path(argumentos.restaurar)
            if not ruta.is_absolute():
                ruta = CARPETA_RESPALDOS / ruta
            respuesta = input(
                f'Esto sustituye la base actual por {ruta.name}. '
                f'Escribe SI para continuar: ')
            if respuesta.strip().upper() != 'SI':
                print('Cancelado.')
                return 1
            restaurar_de_verdad(ruta)
        else:
            copia = respaldar()
            if argumentos.probar:
                print()
                probar_restauracion(copia)
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
