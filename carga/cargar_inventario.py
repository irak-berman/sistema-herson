# -*- coding: utf-8 -*-
"""
Carga inicial del catálogo del Depósito Dental HERSON.

Lee el libro de Excel que el depósito usa hoy y escribe su contenido en
la base, pasando siempre por `src/repositorio.py` y nunca por SQL
directo, para que los disparadores y las reglas del modelo se apliquen.

Qué hace con cada parte del archivo.

- Cada hoja es un proveedor, salvo la primera, que mezcla varios y no
  dice cuál corresponde a cada bloque. Esos productos se cargan sin
  proveedor, que es un campo opcional en el modelo, y se corrigen
  después desde la pantalla de edición.
- La primera columna es un código de proveedor en unas hojas y una
  etiqueta de familia en otras. Si parece código se guarda como
  `clave_proveedor`; si parece familia se convierte en categoría.
- La clave interna la asigna el sistema, porque las del proveedor se
  repiten entre proveedores y no sirven de identificador.
- La existencia inicial entra como un movimiento de tipo entrada,
  nunca como una columna, porque en este modelo la existencia es
  siempre la suma de los movimientos.
- Un precio que describe varias presentaciones, como
  `$300.00 c/u o 2 X $525.00`, se desglosa en el precio unitario del
  producto y una fila de `presentacion` por cada paquete.

Nada se adivina. Un renglón que no se puede interpretar se rechaza y
se reporta con su motivo, porque un costo mal leído se arrastra a todos
los márgenes del negocio.

Uso desde la carpeta del proyecto, con el entorno activado.

    python carga/cargar_inventario.py ARCHIVO.xlsx            ensayo
    python carga/cargar_inventario.py ARCHIVO.xlsx --aplicar  carga

El ensayo no escribe nada en la base. Corre el proceso completo, dice
qué cargaría y produce el mismo reporte, de modo que se puede revisar
antes de tocar nada.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'src'))
sys.path.insert(0, str(RAIZ / 'carga'))

try:
    import openpyxl
except ImportError:
    print('Falta openpyxl. Instálalo con: pip install openpyxl',
          file=sys.stderr)
    raise SystemExit(1)

import repositorio as repo
from conexion import conexion_abierta
from diagnostico_inventario import (COL_CANTIDAD, COL_CLAVE, COL_COSTO,
                                    COL_DESCRIPCION, COL_PRECIO, COLUMNAS,
                                    es_codigo, texto)
from normalizar import a_numero, existencia_minima, leer_cantidad, leer_precio

# Referencia que lleva el movimiento de existencia inicial, para poder
# distinguirlo después de cualquier entrada de mercancía real.
REFERENCIA = 'CARGA INICIAL'

# Unidad base de los productos. El archivo no trae columna de unidad y
# el depósito cuenta casi todo por pieza; lo que no, se ajusta después
# desde la pantalla de edición.
UNIDAD_BASE = 'pieza'

# Categoría a la que van los productos cuya hoja no aporta una familia.
CATEGORIA_SIN_CLASIFICAR = 'Sin clasificar'

# Unidad que se usa para las presentaciones de paquete deducidas del
# precio, cuando el texto no dice de qué se trata.
UNIDAD_PAQUETE = 'paquete'


@dataclass
class Renglon:
    """Un renglón del archivo ya interpretado."""
    hoja: str
    fila: int
    descripcion: str
    clave_proveedor: str | None
    familia: str | None
    proveedor: str | None
    cantidad: float
    costo: float
    precio: float
    paquetes: list = field(default_factory=list)
    notas: list = field(default_factory=list)


@dataclass
class Rechazo:
    hoja: str
    fila: int
    motivo: str
    contenido: str


@dataclass
class Resultado:
    renglones: list = field(default_factory=list)
    rechazos: list = field(default_factory=list)
    categorias: set = field(default_factory=set)
    proveedores: set = field(default_factory=set)


def nombre_de_proveedor(hoja: str) -> str | None:
    """
    Deduce el proveedor a partir del nombre de la hoja.

    Una hoja que nombra a varios proveedores no permite saber cuál
    corresponde a cada renglón, así que devuelve None y esos productos
    quedan sin proveedor hasta que el propietario lo indique.
    """
    limpio = ' '.join(hoja.split())
    if ',' in limpio:
        return None
    # Varias hojas escriben el nombre con espacios entre cada letra,
    # como "U N I S E A L", porque así se ve en el encabezado.
    partes = limpio.split()
    if partes and all(len(p) == 1 for p in partes):
        return ''.join(partes).title()
    return limpio.title()


def interpretar(hoja, resultado: Resultado) -> None:
    """Recorre una hoja y acumula sus renglones interpretados."""
    proveedor = nombre_de_proveedor(hoja.title)
    if proveedor:
        resultado.proveedores.add(proveedor)

    for numero, fila in enumerate(
            hoja.iter_rows(min_row=2, max_col=COLUMNAS, values_only=True),
            start=2):
        if not any(celda not in (None, '') for celda in fila):
            continue
        # Un renglón con solo la primera columna es un separador que
        # marca de qué proveedor viene el bloque siguiente, no un
        # producto.
        if not any(celda not in (None, '') for celda in fila[1:]):
            continue

        descripcion = texto(fila[COL_DESCRIPCION])
        clave = texto(fila[COL_CLAVE])

        if not descripcion:
            # Sin descripción el producto no se puede identificar ni en
            # la pantalla ni en la nota de venta.
            resultado.rechazos.append(Rechazo(
                hoja.title, numero, 'sin descripción',
                f'clave {clave!r}' if clave else 'renglón sin datos útiles'))
            continue

        cantidad, nota_cantidad = leer_cantidad(fila[COL_CANTIDAD])
        if cantidad is None:
            resultado.rechazos.append(Rechazo(
                hoja.title, numero, nota_cantidad, descripcion))
            continue

        costo = a_numero(fila[COL_COSTO])
        precio = leer_precio(fila[COL_PRECIO])

        notas = [n for n in (nota_cantidad,) if n]
        if costo is None:
            if fila[COL_COSTO] not in (None, ''):
                notas.append(f'costo ilegible: '
                             f'{texto(fila[COL_COSTO])!r}, se carga en cero')
            costo = 0.0
        if precio.unitario is None:
            if precio.crudo:
                notas.append(f'precio ilegible: {precio.crudo!r}, '
                             f'se carga en cero')
            precio_unitario = 0.0
        else:
            precio_unitario = precio.unitario

        es_clave = bool(clave) and es_codigo(clave)
        familia = clave if clave and not es_clave else None
        if familia:
            resultado.categorias.add(familia)

        resultado.renglones.append(Renglon(
            hoja=hoja.title, fila=numero, descripcion=descripcion,
            clave_proveedor=clave if es_clave else None,
            familia=familia, proveedor=proveedor,
            cantidad=cantidad, costo=costo, precio=precio_unitario,
            paquetes=precio.paquetes, notas=notas))


def leer_archivo(ruta: Path) -> Resultado:
    """Interpreta el libro completo sin tocar la base."""
    resultado = Resultado()
    libro = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    try:
        for nombre in libro.sheetnames:
            interpretar(libro[nombre], resultado)
    finally:
        libro.close()
    return resultado


def asegurar_catalogos(resultado: Resultado) -> tuple[dict, dict, dict]:
    """
    Crea las categorías, los proveedores y las unidades que falten.

    Devuelve tres diccionarios de nombre a identificador, para no
    consultar la base una vez por renglón.
    """
    unidades = {u['nombre']: u['id_unidad'] for u in repo.listar_unidades()}
    if UNIDAD_BASE not in unidades:
        unidades[UNIDAD_BASE] = repo.crear_unidad(UNIDAD_BASE,
                                                  UNIDAD_BASE + 's')
    if UNIDAD_PAQUETE not in unidades:
        unidades[UNIDAD_PAQUETE] = repo.crear_unidad(UNIDAD_PAQUETE,
                                                     UNIDAD_PAQUETE + 's')

    categorias = {c['nombre']: c['id_categoria']
                  for c in repo.listar_categorias()}
    for nombre in sorted(resultado.categorias | {CATEGORIA_SIN_CLASIFICAR}):
        if nombre not in categorias:
            # La caducidad la decide el propietario por categoría desde
            # la pantalla de catálogo. Aquí entran en falso para no
            # obligar a capturar un lote que nadie conoce.
            categorias[nombre] = repo.crear_categoria(nombre, False)

    proveedores = {p['nombre']: p['id_proveedor']
                   for p in repo.listar_proveedores()}
    for nombre in sorted(resultado.proveedores):
        if nombre not in proveedores:
            proveedores[nombre] = repo.crear_proveedor(nombre)

    return unidades, categorias, proveedores


def cargar(resultado: Resultado) -> dict:
    """
    Escribe los renglones interpretados en la base.

    Todo ocurre dentro de una sola transacción: si algo falla a la
    mitad, la base queda como estaba y no a medio cargar.
    """
    conteo = Counter()

    with conexion_abierta():
        unidades, categorias, proveedores = asegurar_catalogos(resultado)
        conteo['categorias'] = len(categorias)
        conteo['proveedores'] = len(proveedores)

        id_base = unidades[UNIDAD_BASE]
        id_paquete = unidades[UNIDAD_PAQUETE]

        for renglon in resultado.renglones:
            id_categoria = categorias[renglon.familia or
                                      CATEGORIA_SIN_CLASIFICAR]
            id_proveedor = (proveedores.get(renglon.proveedor)
                            if renglon.proveedor else None)

            id_producto = repo.crear_producto(
                descripcion=renglon.descripcion,
                id_categoria=id_categoria,
                id_unidad=id_base,
                id_proveedor=id_proveedor,
                clave_proveedor=renglon.clave_proveedor,
                costo_unitario=renglon.costo,
                precio_venta=renglon.precio,
                existencia_minima=existencia_minima(renglon.cantidad))
            conteo['productos'] += 1

            # La existencia inicial es un movimiento, no una columna.
            if renglon.cantidad > 0:
                repo.registrar_movimiento(
                    id_producto=id_producto, tipo='entrada',
                    cantidad=renglon.cantidad,
                    costo_unitario=renglon.costo or None,
                    referencia=REFERENCIA,
                    observaciones=f'{renglon.hoja}, fila {renglon.fila}',
                    usuario='carga inicial')
                conteo['movimientos'] += 1

            for piezas, importe in renglon.paquetes:
                repo.crear_presentacion(
                    id_producto=id_producto, id_unidad=id_paquete,
                    factor=piezas, precio_venta=importe)
                conteo['presentaciones'] += 1

    return conteo


def escribir_reporte(resultado: Resultado, conteo: dict, origen: Path,
                     destino: Path, aplicado: bool) -> None:
    """Deja por escrito qué se cargó y qué no, con el motivo."""
    total = len(resultado.renglones) + len(resultado.rechazos)
    con_notas = [r for r in resultado.renglones if r.notas]
    sin_proveedor = sum(1 for r in resultado.renglones if not r.proveedor)
    con_paquete = sum(1 for r in resultado.renglones if r.paquetes)
    sin_costo = sum(1 for r in resultado.renglones if not r.costo)
    sin_precio = sum(1 for r in resultado.renglones if not r.precio)

    lineas = [
        '# Reporte de la carga inicial',
        '',
        'Depósito Dental HERSON',
        '',
        f'Archivo de origen: `{origen.name}`',
        f'Fecha: {date.today():%d/%m/%Y}',
        f'Modo: {"carga aplicada a la base" if aplicado else "ensayo, no se escribió nada"}',
        '',
        '---',
        '',
        '## Resumen',
        '',
        f'- Renglones leídos: {total:,}',
        f'- Cargados: {len(resultado.renglones):,}',
        f'- Rechazados: {len(resultado.rechazos):,}',
        f'- Cargados con alguna observación: {len(con_notas):,}',
        '',
        f'- Sin proveedor asignado: {sin_proveedor:,}',
        f'- Con presentación de paquete: {con_paquete:,}',
        f'- Con costo en cero: {sin_costo:,}',
        f'- Con precio en cero: {sin_precio:,}',
        '',
    ]

    if conteo:
        lineas += [
            '## Lo que quedó en la base',
            '',
            f'- Productos: {conteo.get("productos", 0):,}',
            f'- Movimientos de existencia inicial: '
            f'{conteo.get("movimientos", 0):,}',
            f'- Presentaciones: {conteo.get("presentaciones", 0):,}',
            f'- Categorías: {conteo.get("categorias", 0):,}',
            f'- Proveedores: {conteo.get("proveedores", 0):,}',
            '',
        ]

    if resultado.rechazos:
        por_motivo = Counter(r.motivo.split(':')[0] for r in resultado.rechazos)
        lineas += ['## Renglones rechazados', '',
                   'No se cargaron porque no se pudieron interpretar con '
                   'certeza. Se rechazan en lugar de adivinarlos.', '']
        for motivo, cuantos in por_motivo.most_common():
            lineas.append(f'- {motivo}: {cuantos}')
        lineas += ['', '### Detalle', '']
        for r in resultado.rechazos:
            lineas.append(f'- `{r.hoja}` fila {r.fila}: {r.motivo} '
                          f'({r.contenido})')
        lineas.append('')

    if con_notas:
        lineas += ['## Cargados con observación', '',
                   'Entraron a la base, pero algo de su renglón hubo que '
                   'interpretar o quedó incompleto.', '']
        for r in con_notas:
            lineas.append(f'- `{r.hoja}` fila {r.fila}, {r.descripcion}: '
                          f'{"; ".join(r.notas)}')
        lineas.append('')

    if sin_proveedor:
        lineas += [
            '## Productos sin proveedor',
            '',
            f'{sin_proveedor:,} productos quedaron sin proveedor porque su '
            f'hoja menciona varios y el archivo no dice cuál corresponde a '
            f'cada bloque. El campo es opcional en el modelo, de modo que '
            f'la carga no se detiene. Se corrigen desde la pantalla de '
            f'edición cuando el propietario indique a quién pertenece cada '
            f'grupo.',
            '',
        ]

    destino.write_text('\n'.join(lineas) + '\n', encoding='utf-8')


def main() -> int:
    analizador = argparse.ArgumentParser(
        description='Carga inicial del catálogo del depósito.')
    analizador.add_argument('archivo', help='libro de Excel a cargar')
    analizador.add_argument('--aplicar', action='store_true',
                            help='escribe en la base; sin esto solo ensaya')
    analizador.add_argument('-s', '--salida',
                            help='ruta del reporte')
    argumentos = analizador.parse_args()

    origen = Path(argumentos.archivo)
    if not origen.exists():
        print(f'No existe el archivo {origen}', file=sys.stderr)
        return 1

    destino = (Path(argumentos.salida) if argumentos.salida
               else origen.with_name(origen.stem + '_carga.md'))

    resultado = leer_archivo(origen)

    conteo = {}
    if argumentos.aplicar:
        existentes = len(repo.buscar_productos())
        if existentes:
            print(f'La base ya tiene {existentes} productos. La carga '
                  f'inicial está pensada para una base vacía.',
                  file=sys.stderr)
            print('Vacíala con basedatos/crear_base.py o usa otra base.',
                  file=sys.stderr)
            return 1
        conteo = cargar(resultado)

    escribir_reporte(resultado, conteo, origen, destino,
                     argumentos.aplicar)

    print('ENSAYO, no se escribió nada en la base'
          if not argumentos.aplicar else 'CARGA APLICADA')
    print(f'  Renglones leídos : '
          f'{len(resultado.renglones) + len(resultado.rechazos):,}')
    print(f'  Cargados         : {len(resultado.renglones):,}')
    print(f'  Rechazados       : {len(resultado.rechazos):,}')
    print(f'  Con observación  : '
          f'{sum(1 for r in resultado.renglones if r.notas):,}')
    print(f'  Sin proveedor    : '
          f'{sum(1 for r in resultado.renglones if not r.proveedor):,}')
    print(f'  Con presentación : '
          f'{sum(1 for r in resultado.renglones if r.paquetes):,}')
    if conteo:
        print(f'  Productos en base: {conteo.get("productos", 0):,}')
        print(f'  Movimientos      : {conteo.get("movimientos", 0):,}')
        print(f'  Presentaciones   : {conteo.get("presentaciones", 0):,}')
    print()
    print(f'Reporte escrito en {destino}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
