# -*- coding: utf-8 -*-
"""
Prueba funcional del modelo de datos del Depósito Dental HERSON.

Recorre el flujo completo del sistema con datos de ejemplo y verifica
que el modelo se comporte como fue diseñado. Es la evidencia de la
validación descrita en el documento del entregable de la actividad 2.

La prueba corre sobre una base en memoria, de modo que no altera el
archivo herson.db ni deja datos de ejemplo en la base real.

Uso desde la carpeta del proyecto:
    python basedatos/probar_modelo.py

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import sqlite3
import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RUTA_ESQUEMA = CARPETA / 'esquema.sql'

# Datos del producto de ejemplo
EXISTENCIA_INICIAL = 200      # unidades que entran por compra
PIEZAS_POR_CAJA = 100         # factor de conversión de la presentación
COSTO_UNITARIO = 2.50         # pesos por pieza
PRECIO_CAJA = 350.00          # pesos por caja
EXISTENCIA_MINIMA = 15        # unidades base
DIAS_PARA_CADUCAR = 90

resultados = []


def verificar(descripcion: str, obtenido, esperado) -> None:
    """Registra el resultado de una comprobación y lo muestra en pantalla."""
    correcto = obtenido == esperado
    resultados.append(correcto)
    marca = 'OK  ' if correcto else 'FALLA'
    print(f'  [{marca}] {descripcion}')
    if not correcto:
        print(f'          esperado: {esperado}   obtenido: {obtenido}')


def preparar_base() -> sqlite3.Connection:
    """Crea una base en memoria con el esquema del proyecto."""
    conexion = sqlite3.connect(':memory:')
    conexion.executescript(RUTA_ESQUEMA.read_text(encoding='utf-8'))
    conexion.execute('PRAGMA foreign_keys = ON')
    return conexion


def contar_objetos(conexion: sqlite3.Connection) -> tuple:
    """Devuelve cuántas tablas y vistas existen en la base."""
    cursor = conexion.execute("""
        SELECT type, COUNT(*)
        FROM sqlite_master
        WHERE type IN ('table', 'view')
          AND name NOT LIKE 'sqlite_%'
        GROUP BY type
    """)
    conteo = dict(cursor.fetchall())
    return conteo.get('table', 0), conteo.get('view', 0)


def alta_de_catalogo(conexion: sqlite3.Connection) -> None:
    """Registra proveedor, categoría, producto y sus dos presentaciones."""
    conexion.execute("INSERT INTO proveedor (nombre) VALUES ('MOVIDENT')")
    conexion.execute(
        "INSERT INTO categoria (nombre, maneja_caducidad) VALUES ('Desechables', 1)")
    conexion.execute("""
        INSERT INTO producto
            (clave_interna, descripcion, id_categoria, id_proveedor,
             costo_unitario, precio_venta, existencia_minima, maneja_caducidad)
        VALUES ('HER-0001', 'Guante de nitrilo chico', 1, 1, ?, 4.0, ?, 1)
    """, (COSTO_UNITARIO, EXISTENCIA_MINIMA))

    # Dos presentaciones del mismo producto: caja y pieza suelta
    conexion.execute("""
        INSERT INTO presentacion
            (id_producto, nombre, factor, precio_venta, es_predeterminada)
        VALUES (1, 'caja', ?, ?, 0), (1, 'pieza', 1, 4.0, 1)
    """, (PIEZAS_POR_CAJA, PRECIO_CAJA))


def entrada_de_mercancia(conexion: sqlite3.Connection) -> None:
    """Registra un lote con caducidad y la entrada de inventario."""
    conexion.execute("""
        INSERT INTO lote (id_producto, numero_lote, fecha_caducidad)
        VALUES (1, 'L-2027A', date('now', 'localtime', ?))
    """, (f'+{DIAS_PARA_CADUCAR} days',))
    conexion.execute("""
        INSERT INTO movimiento
            (id_producto, id_lote, tipo, cantidad, costo_unitario)
        VALUES (1, 1, 'entrada', ?, ?)
    """, (EXISTENCIA_INICIAL, COSTO_UNITARIO))


def venta_de_mayoreo(conexion: sqlite3.Connection) -> None:
    """Vende una caja completa y descuenta su equivalente en piezas."""
    conexion.execute("""
        INSERT INTO venta (folio, forma_pago, total)
        VALUES ('A-001', 'efectivo', ?)
    """, (PRECIO_CAJA,))
    conexion.execute("""
        INSERT INTO venta_detalle
            (id_venta, id_producto, id_presentacion,
             cantidad, cantidad_base, precio_unitario, importe)
        VALUES (1, 1, 1, 1, ?, ?, ?)
    """, (PIEZAS_POR_CAJA, PRECIO_CAJA, PRECIO_CAJA))
    # La salida de inventario se registra en unidad base, con signo negativo
    conexion.execute("""
        INSERT INTO movimiento
            (id_producto, id_lote, tipo, cantidad, referencia)
        VALUES (1, 1, 'salida', ?, 'A-001')
    """, (-PIEZAS_POR_CAJA,))


def main() -> int:
    print('PRUEBA FUNCIONAL DEL MODELO DE DATOS')
    print('Depósito Dental HERSON · Actividad 2 del cronograma')
    print('=' * 62)

    conexion = preparar_base()

    print('\n1. Creación de la base de datos')
    tablas, vistas = contar_objetos(conexion)
    verificar('Se crearon las 8 tablas del modelo', tablas, 8)
    verificar('Se crearon las 4 vistas del modelo', vistas, 4)
    integridad = conexion.execute('PRAGMA integrity_check').fetchone()[0]
    verificar('La comprobación de integridad es correcta', integridad, 'ok')

    print('\n2. Alta de catálogo')
    alta_de_catalogo(conexion)
    productos = conexion.execute('SELECT COUNT(*) FROM producto').fetchone()[0]
    presentaciones = conexion.execute(
        'SELECT COUNT(*) FROM presentacion').fetchone()[0]
    verificar('Se registró el producto', productos, 1)
    verificar('Se registraron sus dos presentaciones', presentaciones, 2)

    print('\n3. Entrada de mercancía')
    entrada_de_mercancia(conexion)
    existencia = conexion.execute(
        'SELECT existencia FROM v_existencia').fetchone()[0]
    verificar(f'La existencia es de {EXISTENCIA_INICIAL} unidades',
              existencia, float(EXISTENCIA_INICIAL))

    print('\n4. Venta de mayoreo')
    venta_de_mayoreo(conexion)
    esperado = float(EXISTENCIA_INICIAL - PIEZAS_POR_CAJA)
    existencia = conexion.execute(
        'SELECT existencia FROM v_existencia').fetchone()[0]
    verificar(f'Al vender una caja se descontaron {PIEZAS_POR_CAJA} piezas, '
              f'no una', existencia, esperado)

    print('\n5. Alerta de caducidad')
    fila = conexion.execute("""
        SELECT dias_restantes, existencia_lote FROM v_caducidad_proxima
    """).fetchone()
    verificar('El lote aparece en la alerta de caducidad', fila is not None, True)
    if fila:
        verificar(f'Faltan {DIAS_PARA_CADUCAR} días para caducar',
                  fila[0], DIAS_PARA_CADUCAR)
        verificar('El lote conserva 100 unidades vivas', fila[1], esperado)

    print('\n6. Productos por reabastecer')
    pendientes = conexion.execute(
        'SELECT COUNT(*) FROM v_por_reabastecer').fetchone()[0]
    verificar(f'No aparece en la lista, porque hay {int(esperado)} unidades '
              f'y el mínimo es {EXISTENCIA_MINIMA}', pendientes, 0)

    print('\n7. Fuente de datos del tablero')
    fila = conexion.execute("""
        SELECT presentacion, cantidad, cantidad_base, importe, utilidad_estimada
        FROM v_ventas_plano
    """).fetchone()
    utilidad = PRECIO_CAJA - (PIEZAS_POR_CAJA * COSTO_UNITARIO)
    verificar('La venta se exporta con su presentación', fila[0], 'caja')
    verificar('La cantidad se expresa también en unidad base',
              fila[2], float(PIEZAS_POR_CAJA))
    verificar(f'La utilidad estimada es de {utilidad:.0f} pesos',
              fila[4], utilidad)

    conexion.close()

    print('\n' + '=' * 62)
    total = len(resultados)
    correctas = sum(resultados)
    print(f'RESULTADO: {correctas} de {total} comprobaciones correctas')
    if correctas == total:
        print('El modelo se comporta conforme al diseño.')
        return 0
    print('Hay comprobaciones fallidas. Revisar el esquema.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
