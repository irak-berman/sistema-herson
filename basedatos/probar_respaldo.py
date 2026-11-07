# -*- coding: utf-8 -*-
"""
Pruebas del respaldo de la base de datos.

Cada comprobación corresponde a un defecto que se encontró en uso real,
no a un caso imaginado. Se dejan escritas para que no regresen.

Corre sobre una base temporal y no toca la del depósito.

Uso: python basedatos/probar_respaldo.py

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import importlib.util
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent

fallos = []


def comprobar(descripcion: str, condicion: bool, detalle: str = '') -> None:
    if condicion:
        print(f'  ok    {descripcion}')
    else:
        print(f'  FALLA {descripcion}')
        if detalle:
            print(f'        {detalle}')
        fallos.append(descripcion)


def cargar_modulo(carpeta_base: Path):
    """
    Carga respaldo.py apuntándolo a una carpeta de pruebas.

    El módulo calcula sus rutas a partir de su propia ubicación, así
    que se copia a la carpeta temporal y se importa desde ahí.
    """
    destino = carpeta_base / 'respaldo.py'
    shutil.copy(CARPETA / 'respaldo.py', destino)
    spec = importlib.util.spec_from_file_location('respaldo_prueba', destino)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def preparar_base(ruta: Path, productos: int = 50) -> None:
    """Crea una base en modo WAL con datos sin volcar al archivo."""
    cnx = sqlite3.connect(ruta)
    cnx.executescript((RAIZ / 'basedatos' / 'esquema.sql')
                      .read_text(encoding='utf-8'))
    cnx.execute('PRAGMA journal_mode = WAL')
    unidad = cnx.execute('SELECT id_unidad FROM unidad LIMIT 1').fetchone()[0]
    cnx.execute("INSERT INTO categoria (nombre, maneja_caducidad) "
                "VALUES ('Prueba', 1)")
    categoria = cnx.execute("SELECT id_categoria FROM categoria "
                            "WHERE nombre = 'Prueba'").fetchone()[0]
    for i in range(productos):
        cnx.execute('INSERT INTO producto '
                    '(clave_interna, descripcion, id_categoria, id_unidad) '
                    'VALUES (?, ?, ?, ?)',
                    (f'PRU-{i:04d}', f'Producto de prueba {i}',
                     categoria, unidad))
    cnx.commit()
    # A propósito no se cierra: así queda contenido en el WAL, que es la
    # situación real de un respaldo hecho con el sistema abierto.
    return cnx


with tempfile.TemporaryDirectory() as temporal:
    base_pruebas = Path(temporal) / 'basedatos'
    base_pruebas.mkdir()
    ruta_base = base_pruebas / 'herson.db'

    abierta = preparar_base(ruta_base)
    respaldo = cargar_modulo(base_pruebas)

    print('El respaldo captura lo que está en el WAL')
    # Una copia como la del explorador, con el WAL sin volcar.
    copia_cruda = Path(temporal) / 'copia_explorador.db'
    shutil.copy(ruta_base, copia_cruda)
    cnx = sqlite3.connect(f'file:{copia_cruda}?mode=ro', uri=True)
    cuantos_cruda = cnx.execute('SELECT COUNT(*) FROM producto').fetchone()[0]
    cnx.close()

    copia = respaldo.respaldar(verbose=False)
    cnx = sqlite3.connect(f'file:{copia}?mode=ro', uri=True)
    cuantos_copia = cnx.execute('SELECT COUNT(*) FROM producto').fetchone()[0]
    cnx.close()

    comprobar('la copia de archivo pierde lo que está en el WAL',
              cuantos_cruda < 50, f'recuperó {cuantos_cruda} de 50')
    comprobar('backup() recupera todo', cuantos_copia == 50,
              f'recuperó {cuantos_copia} de 50')

    print()
    print('La copia es un archivo solo, sin acompañantes')
    sobrantes = [p.name for p in copia.parent.iterdir()
                 if p.name.startswith(copia.stem)
                 and p.suffix in ('-wal', '-shm', '.parcial')
                 or p.name.endswith(('-wal', '-shm', '.parcial'))]
    comprobar('no quedan archivos -wal, -shm ni .parcial',
              not sobrantes, f'quedaron {sobrantes}')

    print()
    print('Las conexiones se cierran de verdad')
    # Este es el defecto que rompía el respaldo en Windows. Un
    # `with sqlite3.connect(...)` no cierra: solo termina la
    # transacción. La conexión seguía abierta y Windows no deja
    # renombrar un archivo abierto.
    with respaldo._solo_lectura(copia) as cnx_prueba:
        cnx_prueba.execute('SELECT 1')
    try:
        cnx_prueba.execute('SELECT 1')
        cerrada = False
    except sqlite3.ProgrammingError:
        cerrada = True
    comprobar('_solo_lectura cierra la conexión al salir', cerrada,
              'la conexión seguía abierta, en Windows esto impide '
              'renombrar el archivo')

    print()
    print('Las copias ajenas se respetan')
    ajena = copia.parent / 'herson_antes_migracion_001_2026-10-09_195402.db'
    ajena.write_bytes(b'')
    comprobar('no cuenta como respaldo automático',
              ajena not in respaldo.respaldos_existentes())
    comprobar('sí aparece como copia ajena',
              ajena in respaldo.respaldos_ajenos())
    respaldo.listar()
    comprobar('listar no truena con nombres ajenos', True)

    respaldo.COPIAS_A_CONSERVAR = 1
    respaldo.respaldar(verbose=False)
    respaldo.podar()
    comprobar('la poda no borra las copias ajenas', ajena.exists())

    print()
    print('La restauración sirve')
    respaldo.probar_restauracion(copia)
    comprobar('probar_restauracion termina sin error', True)

    abierta.close()

print()
if fallos:
    print(f'{len(fallos)} comprobaciones fallaron.')
    sys.exit(1)
print('Todas las comprobaciones pasaron.')
