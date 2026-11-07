# -*- coding: utf-8 -*-
"""
Verificación de los datos cargados en la base.

Es el entregable que pide la matriz de actividades para la actividad 4,
y es distinto del diagnóstico. El diagnóstico revisa el archivo antes
de cargarlo; esto revisa lo que realmente quedó en la base después, que
es donde pueden aparecer errores que el archivo no tenía: un renglón
que se perdió, una existencia que no corresponde, una clave duplicada,
un producto que quedó colgando de una categoría inexistente.

Vuelve a leer el archivo de origen y lo compara contra la base, en
lugar de confiar en lo que el cargador dijo que hizo. Un cargador que
se verifica a sí mismo no verifica nada.

No modifica nada. Solo lee y reporta.

Uso desde la carpeta del proyecto, con el entorno activado.

    python carga/verificar_carga.py ARCHIVO.xlsx

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'src'))
sys.path.insert(0, str(RAIZ / 'carga'))

from cargar_inventario import REFERENCIA, leer_archivo
from conexion import abrir_conexion

# Cuántos productos se revisan uno por uno contra el archivo. No es una
# muestra estadística: es una comprobación de que la correspondencia
# entre archivo y base se sostiene renglón por renglón y no solo en los
# totales.
TAMANO_MUESTRA = 40


class Comprobacion:
    """Una verificación con su resultado y su detalle."""

    def __init__(self, nombre: str):
        self.nombre = nombre
        self.correcto = True
        self.detalle = ''
        self.diferencias: list[str] = []

    def falla(self, detalle: str, diferencias: list[str] = None) -> None:
        self.correcto = False
        self.detalle = detalle
        self.diferencias = diferencias or []

    def pasa(self, detalle: str = '') -> None:
        self.detalle = detalle


def comprobar_conteo(cnx, esperados: int) -> Comprobacion:
    """Que el número de productos en la base sea el que se cargó."""
    c = Comprobacion('Todos los renglones interpretables llegaron a la base')
    en_base = cnx.execute('SELECT COUNT(*) FROM producto').fetchone()[0]
    if en_base == esperados:
        c.pasa(f'{en_base:,} productos, igual que los renglones cargados')
    else:
        c.falla(f'el archivo daba {esperados:,} renglones cargables y en la '
                f'base hay {en_base:,}, faltan {esperados - en_base:,}')
    return c


def comprobar_claves(cnx) -> Comprobacion:
    """Que ninguna clave interna se repita."""
    c = Comprobacion('Ninguna clave interna está repetida')
    repetidas = cnx.execute("""
        SELECT clave_interna, COUNT(*) AS veces
        FROM producto GROUP BY clave_interna HAVING veces > 1
    """).fetchall()
    if not repetidas:
        total = cnx.execute(
            'SELECT COUNT(DISTINCT clave_interna) FROM producto'
        ).fetchone()[0]
        c.pasa(f'{total:,} claves distintas, una por producto')
    else:
        c.falla(f'{len(repetidas)} claves repetidas',
                [f'{f["clave_interna"]} aparece {f["veces"]} veces'
                 for f in repetidas[:10]])
    return c


def comprobar_referencias(cnx) -> Comprobacion:
    """Que ningún producto cuelgue de una categoría o unidad inexistente."""
    c = Comprobacion('No hay referencias rotas')
    rotas = cnx.execute('PRAGMA foreign_key_check').fetchall()
    if not rotas:
        c.pasa('la comprobación de llaves foráneas del motor no halló nada')
    else:
        c.falla(f'{len(rotas)} referencias rotas',
                [str(tuple(f)) for f in rotas[:10]])
    return c


def comprobar_existencias(cnx, renglones) -> Comprobacion:
    """
    Que la existencia de cada producto sea la cantidad del archivo.

    La existencia no se almacena: es la suma de los movimientos. Esta
    comprobación cierra el circuito, porque verifica que el movimiento
    de carga inicial se registró con la cantidad correcta.
    """
    c = Comprobacion('La existencia de cada producto coincide con el archivo')

    # Se agrupa por descripción y no por producto. Varias descripciones
    # se repiten en el archivo, por ejemplo dos presentaciones del mismo
    # tipo de fresa, y cada una genera su propio producto. Agrupar por
    # producto y luego indexar por descripción dejaría solo el último de
    # cada grupo y haría ver como faltante lo que sí está.
    existencias = {
        f['descripcion']: f['existencia'] for f in cnx.execute("""
            SELECT p.descripcion,
                   COALESCE(SUM(m.cantidad), 0) AS existencia
            FROM producto p
            LEFT JOIN movimiento m ON m.id_producto = p.id_producto
            GROUP BY p.descripcion
        """).fetchall()
    }

    # Del lado del archivo se suma igual, por descripción.
    esperadas = Counter()
    for r in renglones:
        esperadas[r.descripcion] += r.cantidad

    diferencias = []
    for descripcion, cantidad in esperadas.items():
        obtenida = existencias.get(descripcion)
        if obtenida is None:
            diferencias.append(f'{descripcion}: no está en la base')
        elif abs(obtenida - cantidad) > 1e-6:
            diferencias.append(f'{descripcion}: archivo {cantidad:g}, '
                               f'base {obtenida:g}')

    if not diferencias:
        total = sum(esperadas.values())
        c.pasa(f'{len(esperadas):,} descripciones revisadas, '
               f'{total:,.0f} unidades en total')
    else:
        c.falla(f'{len(diferencias)} descripciones con existencia distinta',
                diferencias[:10])
    return c


def comprobar_movimientos(cnx) -> Comprobacion:
    """Que todo movimiento de la carga lleve su referencia y sea entrada."""
    c = Comprobacion('Los movimientos de la carga están bien marcados')
    total = cnx.execute('SELECT COUNT(*) FROM movimiento').fetchone()[0]
    marcados = cnx.execute(
        'SELECT COUNT(*) FROM movimiento WHERE referencia = ?',
        (REFERENCIA,)).fetchone()[0]
    negativos = cnx.execute(
        'SELECT COUNT(*) FROM movimiento WHERE referencia = ? '
        'AND cantidad <= 0', (REFERENCIA,)).fetchone()[0]

    if marcados == total and not negativos:
        c.pasa(f'{marcados:,} movimientos, todos de entrada y con la '
               f'referencia {REFERENCIA}')
    elif negativos:
        c.falla(f'{negativos} movimientos de la carga no son entradas')
    else:
        c.falla(f'{total - marcados} movimientos sin la referencia de carga')
    return c


def comprobar_presentaciones(cnx, renglones) -> Comprobacion:
    """Que cada paquete del archivo tenga su presentación."""
    c = Comprobacion('Las presentaciones de paquete se registraron')
    esperadas = sum(len(r.paquetes) for r in renglones)
    en_base = cnx.execute('SELECT COUNT(*) FROM presentacion').fetchone()[0]
    invalidas = cnx.execute(
        'SELECT COUNT(*) FROM presentacion WHERE factor <= 1 '
        'OR precio_venta <= 0').fetchone()[0]

    if en_base == esperadas and not invalidas:
        c.pasa(f'{en_base} presentaciones, todas con factor mayor a 1 y '
               f'precio positivo')
    elif invalidas:
        c.falla(f'{invalidas} presentaciones con factor o precio inválido')
    else:
        c.falla(f'el archivo daba {esperadas} paquetes y en la base hay '
                f'{en_base}')
    return c


def comprobar_muestra(cnx, renglones) -> tuple[Comprobacion, list]:
    """
    Revisa una muestra renglón por renglón contra el archivo.

    Los totales pueden cuadrar y aun así estar cruzados los datos entre
    productos, así que se revisa una muestra campo por campo. Se toma
    repartida a lo largo del archivo y no al azar, para que la
    comprobación sea repetible.
    """
    c = Comprobacion('La muestra revisada campo por campo corresponde')
    if not renglones:
        c.falla('no hay renglones que revisar')
        return c, []

    paso = max(1, len(renglones) // TAMANO_MUESTRA)
    muestra = renglones[::paso][:TAMANO_MUESTRA]

    diferencias, revisados = [], []
    for r in muestra:
        fila = cnx.execute("""
            SELECT p.clave_interna, p.descripcion, p.costo_unitario,
                   p.precio_venta, p.clave_proveedor, p.existencia_minima,
                   COALESCE(SUM(m.cantidad), 0) AS existencia
            FROM producto p
            LEFT JOIN movimiento m ON m.id_producto = p.id_producto
            WHERE p.descripcion = ?
            GROUP BY p.id_producto LIMIT 1
        """, (r.descripcion,)).fetchone()

        if fila is None:
            diferencias.append(f'{r.descripcion}: no está en la base')
            continue
        if abs(fila['costo_unitario'] - r.costo) > 0.005:
            diferencias.append(f'{r.descripcion}: costo archivo {r.costo}, '
                               f'base {fila["costo_unitario"]}')
        if abs(fila['precio_venta'] - r.precio) > 0.005:
            diferencias.append(f'{r.descripcion}: precio archivo {r.precio}, '
                               f'base {fila["precio_venta"]}')
        if (r.clave_proveedor or None) != (fila['clave_proveedor'] or None):
            diferencias.append(
                f'{r.descripcion}: clave de proveedor archivo '
                f'{r.clave_proveedor!r}, base {fila["clave_proveedor"]!r}')
        revisados.append((fila['clave_interna'], r.descripcion))

    if not diferencias:
        c.pasa(f'{len(muestra)} productos revisados campo por campo, sin '
               f'diferencias')
    else:
        c.falla(f'{len(diferencias)} diferencias en la muestra',
                diferencias[:10])
    return c, revisados


def escribir_reporte(comprobaciones, revisados, origen: Path,
                     destino: Path) -> None:
    """Deja la verificación por escrito."""
    pasaron = sum(1 for c in comprobaciones if c.correcto)

    lineas = [
        '# Verificación de los datos cargados en la base',
        '',
        'Depósito Dental HERSON',
        '',
        f'Archivo de origen: `{origen.name}`',
        f'Fecha: {date.today():%d/%m/%Y}',
        '',
        'Generado por `carga/verificar_carga.py`. El archivo vuelve a '
        'leerse y se compara contra la base: no se confía en lo que el '
        'cargador reportó, porque un cargador que se verifica a sí mismo '
        'no verifica nada.',
        '',
        '---',
        '',
        '## Resultado',
        '',
        f'{pasaron} de {len(comprobaciones)} comprobaciones correctas.',
        '',
    ]

    for c in comprobaciones:
        marca = 'Correcto' if c.correcto else 'FALLA'
        lineas += [f'### {c.nombre}', '', f'**{marca}.** {c.detalle}', '']
        if c.diferencias:
            for d in c.diferencias:
                lineas.append(f'- {d}')
            lineas.append('')

    if revisados:
        lineas += [
            '## Productos de la muestra',
            '',
            f'Se revisaron {len(revisados)} productos campo por campo, '
            f'repartidos a lo largo del archivo para que la comprobación '
            f'sea repetible y no dependa del azar. Se comparó la '
            f'descripción, el costo, el precio y la clave del proveedor.',
            '',
        ]
        for clave, descripcion in revisados:
            lineas.append(f'- `{clave}` {descripcion}')
        lineas.append('')

    destino.write_text('\n'.join(lineas) + '\n', encoding='utf-8')


def main() -> int:
    analizador = argparse.ArgumentParser(
        description='Verifica los datos cargados en la base contra el '
                    'archivo de origen.')
    analizador.add_argument('archivo', help='libro de Excel de origen')
    analizador.add_argument('-s', '--salida', help='ruta del reporte')
    argumentos = analizador.parse_args()

    origen = Path(argumentos.archivo)
    if not origen.exists():
        print(f'No existe el archivo {origen}', file=sys.stderr)
        return 1

    destino = (Path(argumentos.salida) if argumentos.salida
               else origen.with_name(origen.stem + '_verificacion.md'))

    resultado = leer_archivo(origen)
    cnx = abrir_conexion()
    try:
        comprobaciones = [
            comprobar_conteo(cnx, len(resultado.renglones)),
            comprobar_claves(cnx),
            comprobar_referencias(cnx),
            comprobar_existencias(cnx, resultado.renglones),
            comprobar_movimientos(cnx),
            comprobar_presentaciones(cnx, resultado.renglones),
        ]
        muestra, revisados = comprobar_muestra(cnx, resultado.renglones)
        comprobaciones.append(muestra)
    finally:
        cnx.close()

    escribir_reporte(comprobaciones, revisados, origen, destino)

    for c in comprobaciones:
        print(f'  {"ok   " if c.correcto else "FALLA"} {c.nombre}')
        if c.detalle:
            print(f'        {c.detalle}')
        for d in c.diferencias[:5]:
            print(f'        - {d}')
    print()
    print(f'Reporte escrito en {destino}')

    return 0 if all(c.correcto for c in comprobaciones) else 1


if __name__ == '__main__':
    raise SystemExit(main())
