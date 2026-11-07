# -*- coding: utf-8 -*-
"""
Diagnóstico del archivo de inventario del Depósito Dental HERSON.

Recorre el libro de Excel que el depósito usa hoy, una hoja por
proveedor, y escribe un reporte con todo lo que impide cargarlo tal
cual a la base de datos. No modifica el archivo ni toca la base: solo
mira y reporta.

Es el primer paso de la actividad 4 del cronograma y la evidencia de la
verificación de los datos que pide el entregable. El criterio de
corrección se decide a partir de este reporte, no al revés.

Uso desde la carpeta del proyecto, con el entorno activado.

    python carga/diagnostico_inventario.py ruta/al/inventario.xlsx

El reporte se escribe junto al archivo analizado, con el mismo nombre
y la terminación _diagnostico.md, y un resumen sale por pantalla.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print('Falta openpyxl. Instálalo con: pip install openpyxl',
          file=sys.stderr)
    raise SystemExit(1)

# ---------------------------------------------------------------------
# Posición de las columnas
#
# Las nueve hojas no comparten los encabezados al pie de la letra, pero
# sí el orden de las columnas, que es lo que se aprovecha aquí. Los
# encabezados varían entre "ID", "CODIGO", "CODIGO BORGATTA" y el nombre
# del proveedor con espacios intercalados, así que leerlos por nombre
# sería más frágil que leerlos por posición.
# ---------------------------------------------------------------------
COL_CLAVE = 0
COL_DESCRIPCION = 1
COL_CANTIDAD = 2
COL_COSTO = 3
COL_PRECIO = 4
COLUMNAS = 6

# Un valor de la primera columna se toma por código de proveedor cuando
# tiene forma de código: dígitos con separador, o una cadena puramente
# numérica de tres o más dígitos. Lo demás se trata como etiqueta de
# familia, que es como el depósito usa esa columna en varias hojas.
PATRON_CODIGO = re.compile(r'^(?:[A-Za-z]{0,4}\d[A-Za-z0-9]*[-/.][A-Za-z0-9\-/.]+|\d{3,})$')

# Señales de que el precio no es un número sino una lista de
# presentaciones escrita a mano: "2 x $525.00", "$135 o 2 x $220",
# "$300.00 c/u".
PATRON_MAYOREO = re.compile(r'\d\s*[xX]\s*\$?\s*\d|c/\s*u|\bo\b\s*\d|\bo\b\s*\$')


@dataclass
class Hallazgos:
    """Lo que se encontró en una hoja."""
    hoja: str
    renglones: int = 0
    sin_clave: int = 0
    sin_descripcion: int = 0
    sin_costo: int = 0
    sin_precio: int = 0
    cantidad_no_numerica: int = 0
    costo_no_numerico: int = 0
    precio_no_numerico: int = 0
    precio_con_mayoreo: int = 0
    codigos_repetidos: dict = field(default_factory=dict)
    familias_repetidas: dict = field(default_factory=dict)
    separadores: list = field(default_factory=list)

    @property
    def renglones_codigo_repetido(self) -> int:
        return sum(self.codigos_repetidos.values())

    @property
    def renglones_familia_repetida(self) -> int:
        return sum(self.familias_repetidas.values())


def texto(valor) -> str:
    """Normaliza una celda a texto sin espacios de sobra."""
    return '' if valor is None else str(valor).strip()


def es_numero(valor) -> bool:
    """
    Indica si la celda se puede leer como número.

    El archivo trae cantidades como "1c/ 0 pzs" y precios como
    "30cmX $10", que Excel guarda como texto y que ninguna conversión
    directa puede interpretar.
    """
    if valor is None:
        return False
    if isinstance(valor, (int, float)):
        return True
    limpio = texto(valor).replace(',', '').replace('$', '').strip()
    if not limpio:
        return False
    try:
        float(limpio)
        return True
    except ValueError:
        return False


def es_codigo(valor: str) -> bool:
    """Distingue un código de proveedor de una etiqueta de familia."""
    return bool(PATRON_CODIGO.match(valor))


def analizar_hoja(hoja) -> Hallazgos:
    """Perfila una hoja del libro."""
    resultado = Hallazgos(hoja=hoja.title)

    filas = []
    for fila in hoja.iter_rows(min_row=2, max_col=COLUMNAS, values_only=True):
        if not any(celda not in (None, '') for celda in fila):
            continue
        # Un renglón que solo trae la primera columna no es un producto,
        # es un separador que el depósito usa para marcar de qué
        # proveedor viene el bloque que sigue.
        if not any(celda not in (None, '') for celda in fila[1:]):
            resultado.separadores.append(texto(fila[COL_CLAVE]))
            continue
        filas.append(fila)

    resultado.renglones = len(filas)
    if not filas:
        return resultado

    for fila in filas:
        if not texto(fila[COL_CLAVE]):
            resultado.sin_clave += 1
        if not texto(fila[COL_DESCRIPCION]):
            resultado.sin_descripcion += 1
        if fila[COL_COSTO] in (None, ''):
            resultado.sin_costo += 1
        elif not es_numero(fila[COL_COSTO]):
            resultado.costo_no_numerico += 1
        if fila[COL_PRECIO] in (None, ''):
            resultado.sin_precio += 1
        elif not es_numero(fila[COL_PRECIO]):
            resultado.precio_no_numerico += 1
        if fila[COL_CANTIDAD] is not None and not es_numero(fila[COL_CANTIDAD]):
            resultado.cantidad_no_numerica += 1
        if PATRON_MAYOREO.search(texto(fila[COL_PRECIO])):
            resultado.precio_con_mayoreo += 1

    # Las claves que se repiten se separan en dos grupos, porque
    # significan cosas distintas y se corrigen de forma distinta. Un
    # código de proveedor repetido es un posible duplicado y hay que
    # verlo a mano. Una etiqueta de familia repetida no es un
    # duplicado: son productos distintos del mismo tipo.
    conteo = Counter(texto(f[COL_CLAVE]) for f in filas if texto(f[COL_CLAVE]))
    for clave, veces in conteo.items():
        if veces < 2:
            continue
        if es_codigo(clave):
            resultado.codigos_repetidos[clave] = veces
        else:
            resultado.familias_repetidas[clave] = veces

    return resultado


def renglon_lista(etiqueta: str, cantidad: int, total: int) -> str:
    """Una línea del reporte con su porcentaje."""
    if total == 0:
        return f'- {etiqueta}: {cantidad}'
    return f'- {etiqueta}: {cantidad} ({cantidad / total:.0%})'


def escribir_reporte(todas: list[Hallazgos], origen: Path,
                     destino: Path) -> None:
    """Arma el reporte en Markdown."""
    con_datos = [h for h in todas if h.renglones]
    vacias = [h for h in todas if not h.renglones]
    total = sum(h.renglones for h in con_datos)

    def suma(campo: str) -> int:
        return sum(getattr(h, campo) for h in con_datos)

    lineas = [
        '# Diagnóstico del archivo de inventario',
        '',
        'Depósito Dental HERSON',
        '',
        f'Archivo analizado: `{origen.name}`',
        f'Fecha del diagnóstico: {date.today():%d/%m/%Y}',
        '',
        'Generado por `carga/diagnostico_inventario.py`. El archivo de '
        'origen no se modificó.',
        '',
        '---',
        '',
        '## Resumen',
        '',
        f'- Hojas en el libro: {len(todas)}, de las cuales '
        f'{len(con_datos)} tienen datos',
        f'- Renglones con datos: {total:,}',
        '',
        '### Campos incompletos',
        '',
        renglon_lista('Sin clave en la primera columna',
                      suma('sin_clave'), total),
        renglon_lista('Sin descripción', suma('sin_descripcion'), total),
        renglon_lista('Sin costo de compra', suma('sin_costo'), total),
        renglon_lista('Sin precio de venta', suma('sin_precio'), total),
        '',
        '### Valores que no son números',
        '',
        renglon_lista('Cantidad escrita como texto',
                      suma('cantidad_no_numerica'), total),
        renglon_lista('Costo escrito como texto',
                      suma('costo_no_numerico'), total),
        renglon_lista('Precio escrito como texto',
                      suma('precio_no_numerico'), total),
        '',
        renglon_lista('Precio que describe varias presentaciones',
                      suma('precio_con_mayoreo'), total),
        '',
        'El precio con varias presentaciones no es un error de captura. '
        'Es la forma en que el depósito registra el mayoreo, por ejemplo '
        '`$300.00 c/u o 2 X $525.00`. Esos renglones alimentan la tabla '
        '`presentacion` del modelo, con su factor de conversión y su '
        'precio propio, y no se pueden cargar como un solo número.',
        '',
        '### Claves repetidas',
        '',
        f'- Códigos de proveedor repetidos: '
        f'{sum(len(h.codigos_repetidos) for h in con_datos)} claves en '
        f'{suma("renglones_codigo_repetido")} renglones',
        f'- Etiquetas de familia repetidas: '
        f'{sum(len(h.familias_repetidas) for h in con_datos)} etiquetas en '
        f'{suma("renglones_familia_repetida")} renglones',
        '',
        'La distinción importa porque las dos se corrigen distinto. Un '
        'código de proveedor repetido puede ser un producto capturado dos '
        'veces y hay que revisarlo a mano. Una etiqueta de familia '
        'repetida no es un duplicado: son productos distintos del mismo '
        'tipo, y esa etiqueta alimenta la tabla `categoria`, no la clave '
        'del producto.',
        '',
        '---',
        '',
        '## Detalle por hoja',
        '',
    ]

    for h in con_datos:
        lineas += [
            f'### {h.hoja}',
            '',
            f'{h.renglones:,} renglones con datos.',
            '',
        ]
        problemas = [
            ('sin clave', h.sin_clave),
            ('sin descripción', h.sin_descripcion),
            ('sin costo', h.sin_costo),
            ('sin precio', h.sin_precio),
            ('cantidad como texto', h.cantidad_no_numerica),
            ('costo como texto', h.costo_no_numerico),
            ('precio como texto', h.precio_no_numerico),
            ('precio con varias presentaciones', h.precio_con_mayoreo),
        ]
        hay = [f'- {etiqueta}: {n}' for etiqueta, n in problemas if n]
        lineas += hay if hay else ['- Sin incidencias en los campos.']
        lineas.append('')

        if h.codigos_repetidos:
            lineas.append('Códigos de proveedor repetidos, revisar a mano.')
            lineas.append('')
            for clave, veces in sorted(h.codigos_repetidos.items(),
                                       key=lambda kv: -kv[1]):
                lineas.append(f'- `{clave}` aparece {veces} veces')
            lineas.append('')

        if h.familias_repetidas:
            top = sorted(h.familias_repetidas.items(),
                         key=lambda kv: -kv[1])[:10]
            lineas.append(
                f'Etiquetas de familia más frecuentes, de '
                f'{len(h.familias_repetidas)} distintas. No son duplicados.')
            lineas.append('')
            for clave, veces in top:
                lineas.append(f'- `{clave}` en {veces} renglones')
            lineas.append('')

        if h.separadores:
            lineas += [
                f'Renglones separadores, que marcan el proveedor del bloque '
                f'siguiente: {", ".join(repr(s) for s in h.separadores)}.',
                '',
            ]

    if vacias:
        lineas += [
            '### Hojas sin datos',
            '',
            ', '.join(h.hoja for h in vacias) + '.',
            '',
        ]

    # La hoja que concentra la mayor parte del catálogo merece una
    # advertencia propia, porque es donde está el problema que no se
    # puede resolver leyendo el archivo.
    mayor = max(con_datos, key=lambda h: h.renglones, default=None)
    if mayor and len(mayor.hoja.split(',')) > 1:
        lineas += [
            '---',
            '',
            '## Lo que el archivo no alcanza a decir',
            '',
            f'La hoja `{mayor.hoja}` concentra {mayor.renglones:,} de los '
            f'{total:,} renglones y su nombre menciona '
            f'{len(mayor.hoja.split(","))} proveedores, pero adentro solo '
            f'hay {len(mayor.separadores)} renglones separadores. Para la '
            f'mayoría de esos productos el archivo no dice de qué '
            f'proveedor son.',
            '',
            'Eso no se puede deducir del archivo y tiene que decidirlo el '
            'propietario, ya sea indicando dónde empieza y termina cada '
            'bloque, o aceptando que esos productos se carguen sin '
            'proveedor y se vayan corrigiendo desde la pantalla de '
            'edición. El campo de proveedor es opcional en el modelo, de '
            'modo que la carga no se detiene por esto.',
            '',
        ]

    destino.write_text('\n'.join(lineas) + '\n', encoding='utf-8')


def main() -> int:
    analizador = argparse.ArgumentParser(
        description='Diagnostica el archivo de inventario del depósito '
                    'antes de la carga inicial.')
    analizador.add_argument('archivo',
                            help='ruta del libro de Excel a analizar')
    analizador.add_argument('-s', '--salida',
                            help='ruta del reporte (por omisión, junto al '
                                 'archivo analizado)')
    argumentos = analizador.parse_args()

    origen = Path(argumentos.archivo)
    if not origen.exists():
        print(f'No existe el archivo {origen}', file=sys.stderr)
        return 1

    destino = (Path(argumentos.salida) if argumentos.salida
               else origen.with_name(origen.stem + '_diagnostico.md'))

    libro = openpyxl.load_workbook(origen, data_only=True, read_only=True)
    todas = [analizar_hoja(libro[nombre]) for nombre in libro.sheetnames]
    libro.close()

    escribir_reporte(todas, origen, destino)

    con_datos = [h for h in todas if h.renglones]
    total = sum(h.renglones for h in con_datos)
    print(f'Hojas con datos: {len(con_datos)} de {len(todas)}')
    print(f'Renglones con datos: {total:,}')
    print(f'Sin clave: {sum(h.sin_clave for h in con_datos)}')
    print(f'Sin descripción: {sum(h.sin_descripcion for h in con_datos)}')
    print(f'Precio con varias presentaciones: '
          f'{sum(h.precio_con_mayoreo for h in con_datos)}')
    print(f'Códigos de proveedor repetidos: '
          f'{sum(h.renglones_codigo_repetido for h in con_datos)} renglones')
    print(f'Etiquetas de familia repetidas: '
          f'{sum(h.renglones_familia_repetida for h in con_datos)} renglones')
    print()
    print(f'Reporte escrito en {destino}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
