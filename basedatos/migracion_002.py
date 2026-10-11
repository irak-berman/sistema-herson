# -*- coding: utf-8 -*-
"""
Migración 002. Estado de cancelación de la venta.

Corrige un defecto que se detectó al probar el botón de cancelar en la
pantalla de venta.

Una venta cancelada se marcaba escribiendo la palabra CANCELADA al
principio de las observaciones y poniendo el total del encabezado en
cero. El detalle de la nota quedaba intacto, y como la vista que
alimenta el tablero suma los renglones y no el encabezado, la venta
cancelada seguía contando como ingreso y como utilidad. En una prueba,
una nota de 1,650 pesos cancelada seguía apareciendo completa en el
total del tablero.

Son dos problemas distintos.

El estado del negocio vivía dentro de un campo de texto libre. Para
saber si una venta estaba cancelada había que leer el principio de las
observaciones, y bastaba con que alguien escribiera algo antes para
que dejara de reconocerse. Ahora hay una columna.

El total del encabezado se ponía en cero, lo que lo dejaba en
desacuerdo con la suma de sus renglones. Con los disparadores de la
migración anterior ese número se recalcula solo, así que la
cancelación ya no lo toca: lo que saca la venta del análisis es la
marca, no un total falseado.

Las ventas canceladas que ya existían se identifican por el texto
anterior y se convierten a la columna nueva.

Uso desde la carpeta del proyecto:
    python basedatos/migracion_002.py

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_BASE = RAIZ_PROYECTO / 'basedatos' / 'herson.db'
CARPETA_RESPALDOS = RAIZ_PROYECTO / 'basedatos' / 'respaldos'

VISTA_VENTAS_PLANO = """
CREATE VIEW v_ventas_plano AS
SELECT
    v.id_venta,
    v.folio,
    date(v.fecha)                        AS fecha,
    v.cliente,
    v.forma_pago,
    p.clave_interna,
    p.descripcion,
    c.nombre                             AS categoria,
    pr.nombre                            AS proveedor,
    COALESCE(up.nombre, u.nombre)        AS presentacion,
    v.usuario,
    d.cantidad,
    d.cantidad_base,
    d.precio_unitario,
    (d.cantidad * d.precio_unitario)                 AS importe_bruto,
    d.descuento,
    d.importe,
    p.costo_unitario,
    d.importe - (d.cantidad_base * p.costo_unitario) AS utilidad_estimada
FROM venta_detalle d
JOIN venta    v ON v.id_venta    = d.id_venta
JOIN producto p ON p.id_producto = d.id_producto
JOIN unidad   u ON u.id_unidad   = p.id_unidad
LEFT JOIN categoria    c    ON c.id_categoria       = p.id_categoria
LEFT JOIN proveedor    pr   ON pr.id_proveedor      = p.id_proveedor
LEFT JOIN presentacion pres ON pres.id_presentacion = d.id_presentacion
LEFT JOIN unidad       up   ON up.id_unidad         = pres.id_unidad
WHERE v.cancelada = 0
"""

COLUMNAS_NUEVAS = (
    ('cancelada',
     "INTEGER NOT NULL DEFAULT 0 CHECK (cancelada IN (0, 1))"),
    ('fecha_cancelacion',   'TEXT'),
    ('usuario_cancelacion', 'TEXT'),
    ('motivo_cancelacion',  'TEXT'),
)


def columnas_de(conexion: sqlite3.Connection, tabla: str) -> set:
    """Nombres de las columnas de una tabla."""
    return {fila[1]
            for fila in conexion.execute(f'PRAGMA table_info({tabla})')}


def respaldar(ruta: Path) -> Path:
    """
    Copia la base antes de modificarla y devuelve la ruta de la copia.

    Se usa la función backup de sqlite3 y no una copia de archivo,
    porque la base opera en modo WAL y las escrituras recientes pueden
    estar todavía en los archivos auxiliares.
    """
    CARPETA_RESPALDOS.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    destino = CARPETA_RESPALDOS / f'herson_antes_migracion_002_{marca}.db'

    origen = sqlite3.connect(ruta)
    copia = sqlite3.connect(destino)
    with copia:
        origen.backup(copia)
    copia.close()
    origen.close()
    return destino


def aplicar(ruta: Path = RUTA_BASE) -> None:
    """Aplica los cambios que falten y reporta lo que hizo."""
    if not ruta.exists():
        print(f'No se encontró la base en {ruta}')
        print('Si todavía no existe, ejecute basedatos/crear_base.py,')
        print('que ya crea el esquema nuevo y no necesita migraciones.')
        sys.exit(1)

    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row

    if 'usuario' not in columnas_de(conexion, 'venta'):
        print('Esta base todavía no tiene la migración 001.')
        print('Ejecute primero basedatos/migracion_001.py')
        conexion.close()
        sys.exit(1)

    faltantes = [nombre for nombre, _ in COLUMNAS_NUEVAS
                 if nombre not in columnas_de(conexion, 'venta')]

    if not faltantes:
        print('La base ya tiene el estado de cancelación. '
              'No hay nada que hacer.')
        conexion.close()
        return

    print('Cambios por aplicar:')
    for nombre in faltantes:
        print(f'  - columna {nombre} en venta')
    print('  - v_ventas_plano deja fuera las ventas canceladas')
    print()

    copia = respaldar(ruta)
    print(f'Respaldo previo: {copia.name}')
    print()

    try:
        with conexion:
            for nombre, definicion in COLUMNAS_NUEVAS:
                if nombre in faltantes:
                    conexion.execute(
                        f'ALTER TABLE venta ADD COLUMN {nombre} {definicion}')

            # Las canceladas de antes se reconocen por el texto con que
            # se marcaban, y se pasan a la columna nueva. Después de
            # esto la marca de texto deja de usarse.
            conexion.execute("""
                UPDATE venta
                   SET cancelada = 1,
                       motivo_cancelacion = observaciones,
                       usuario_cancelacion = 'sin identificar'
                 WHERE observaciones LIKE 'CANCELADA%'
            """)
            convertidas = conexion.total_changes

            # El total del encabezado se puso en cero al cancelar y
            # quedó en desacuerdo con el detalle. Se recalcula para que
            # vuelva a cuadrar; lo que saca la venta del análisis es la
            # marca, no el total.
            conexion.execute("""
                UPDATE venta
                   SET total = (SELECT COALESCE(SUM(importe), 0)
                                  FROM venta_detalle
                                 WHERE id_venta = venta.id_venta),
                       descuento = (SELECT COALESCE(SUM(descuento), 0)
                                      FROM venta_detalle
                                     WHERE id_venta = venta.id_venta)
                 WHERE EXISTS (SELECT 1 FROM venta_detalle
                                WHERE id_venta = venta.id_venta)
            """)

            conexion.execute('DROP VIEW IF EXISTS v_ventas_plano')
            conexion.execute(VISTA_VENTAS_PLANO)

    except sqlite3.Error as error:
        conexion.close()
        print(f'La migración falló y no se guardó ningún cambio: {error}')
        print(f'La base quedó como estaba. El respaldo está en {copia}')
        sys.exit(1)

    canceladas = conexion.execute(
        'SELECT COUNT(*) FROM venta WHERE cancelada = 1').fetchone()[0]
    vigentes = conexion.execute(
        'SELECT COUNT(*) FROM venta WHERE cancelada = 0').fetchone()[0]
    integridad = conexion.execute('PRAGMA integrity_check').fetchone()[0]
    total = conexion.execute(
        'SELECT COALESCE(SUM(importe), 0) FROM v_ventas_plano').fetchone()[0]
    conexion.close()

    print('Aplicado.')
    print()
    print(f'Integridad del archivo: {integridad}')
    print(f'Ventas vigentes: {vigentes}')
    print(f'Ventas canceladas: {canceladas}')
    print(f'Total que reporta ahora el tablero: {total:,.2f}')
    if canceladas:
        print('(ya sin las canceladas, que antes sí se contaban)')


if __name__ == '__main__':
    aplicar()
