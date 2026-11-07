# -*- coding: utf-8 -*-
"""
Normalización de los valores del archivo de inventario del depósito.

El libro de Excel se llenó a mano durante años, así que las cantidades,
los costos y los precios no siempre son números. Hay cantidades como
"1c/ 0 pzs", precios como "30cmX $10" y, sobre todo, precios que
describen varias presentaciones a la vez, como
"$300.00 c/u o 2 X $525.00".

Este módulo convierte esos textos en valores que la base puede recibir,
y cuando no puede lo dice en lugar de inventar un número. La regla es
que un valor dudoso se reporta, nunca se adivina: un costo mal leído se
arrastra a todos los márgenes del negocio.

Se mantiene aparte del cargador para poderlo probar solo.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

# Un importe dentro de un texto: 1,234.50 o 450 o .50
PATRON_IMPORTE = re.compile(r'\d[\d,]*\.?\d*')

# "2 x $525.00", "2x1110", "3 X 100". El primer número es cuántas
# piezas lleva el paquete y el segundo lo que cuesta el paquete.
PATRON_PAQUETE = re.compile(
    r'(\d+)\s*[xX]\s*\$?\s*(\d[\d,]*\.?\d*)')

# "c/u" y sus variantes marcan el precio por pieza suelta.
PATRON_UNITARIO = re.compile(r'c\s*/\s*u', re.IGNORECASE)


@dataclass
class Precio:
    """
    El resultado de leer la celda de precio.

    unitario es el precio por pieza, si el texto lo da.
    paquetes son los pares (piezas, precio del paquete) encontrados.
    crudo es el texto original, que se conserva para el reporte.
    """
    unitario: float | None = None
    paquetes: list[tuple[int, float]] = None
    crudo: str = ''

    def __post_init__(self):
        if self.paquetes is None:
            self.paquetes = []

    @property
    def interpretable(self) -> bool:
        return self.unitario is not None or bool(self.paquetes)


def a_numero(valor) -> float | None:
    """
    Lee un número de una celda, o devuelve None si no se puede.

    Acepta lo que Excel guardó como número y los textos que son un
    número con adornos, como "$1,234.50" o "450 ". No intenta rescatar
    un número de un texto que dice otra cosa, porque ahí la
    probabilidad de equivocarse es alta y el costo de equivocarse
    también.
    """
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    if not texto:
        return None

    limpio = texto.replace('$', '').replace(',', '').strip()
    try:
        return float(limpio)
    except ValueError:
        pass

    # Un texto con un solo número adentro y poco ruido alrededor se
    # puede leer con confianza razonable, por ejemplo "5 pzs" o
    # "aprox 120". Con dos o más números ya no, porque no hay forma de
    # saber cuál es el bueno.
    encontrados = PATRON_IMPORTE.findall(texto)
    if len(encontrados) == 1:
        try:
            return float(encontrados[0].replace(',', ''))
        except ValueError:
            return None
    return None


def leer_cantidad(valor) -> tuple[float | None, str | None]:
    """
    Lee la cantidad en existencia.

    Devuelve la cantidad y, si hubo que interpretar algo, una nota que
    explica qué se hizo, para que quede en el reporte de carga.
    """
    if valor is None or str(valor).strip() == '':
        return 0.0, 'sin cantidad en el archivo, se carga en cero'

    numero = a_numero(valor)
    if numero is None:
        return None, f'cantidad ilegible: {str(valor).strip()!r}'
    if numero < 0:
        return None, f'cantidad negativa: {numero}'

    if not isinstance(valor, (int, float)):
        return numero, (f'cantidad interpretada como {numero:g} '
                        f'desde {str(valor).strip()!r}')
    return numero, None


def leer_precio(valor) -> Precio:
    """
    Lee la celda de precio de venta, que puede traer varias
    presentaciones.

    Ejemplos reales del archivo del depósito.

        450                       -> unitario 450
        $300.00 c/u o 2 X $525.00 -> unitario 300, paquete de 2 en 525
        $580/ 2x $1110            -> unitario 580, paquete de 2 en 1110
        $135 o 2 x $220           -> unitario 135, paquete de 2 en 220
    """
    if valor is None:
        return Precio(crudo='')
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return Precio(unitario=float(valor), crudo=str(valor))

    texto = str(valor).strip()
    if not texto:
        return Precio(crudo='')

    paquetes = []
    unitario_de_paquete = None
    for piezas, importe in PATRON_PAQUETE.findall(texto):
        try:
            cantidad = int(piezas)
            monto = float(importe.replace(',', ''))
        except ValueError:
            continue
        if monto <= 0:
            continue
        if cantidad > 1:
            paquetes.append((cantidad, monto))
        elif unitario_de_paquete is None:
            # "1 X $900.00" no es una presentación, es el precio
            # unitario escrito con la misma forma que los paquetes. El
            # depósito escribe así cuando enlista las dos opciones
            # juntas, por ejemplo '1x $340 o 2x $600'.
            unitario_de_paquete = monto

    # El precio unitario es el primer importe que no forme parte de un
    # paquete ya reconocido. Se quitan del texto los paquetes y se
    # busca en lo que queda.
    restante = PATRON_PAQUETE.sub(' ', texto)
    importes = [float(i.replace(',', ''))
                for i in PATRON_IMPORTE.findall(restante)
                if i.strip('.,')]

    unitario = None
    if importes:
        # Con "c/u" el número que acompaña es explícitamente el
        # unitario. Sin esa marca, se toma el primero, que es como el
        # depósito escribe estas celdas.
        unitario = importes[0]
    elif unitario_de_paquete is not None:
        unitario = unitario_de_paquete
    elif not paquetes:
        return Precio(crudo=texto)

    if unitario is not None and unitario <= 0:
        unitario = None

    return Precio(unitario=unitario, paquetes=paquetes, crudo=texto)


def existencia_minima(cantidad: float) -> int:
    """
    Calcula la existencia mínima inicial de un producto.

    Quince por ciento de la existencia de la carga inicial, redondeado
    hacia arriba y nunca menor a uno, que es el criterio acordado con
    el propietario y el mismo que documenta el modelo de datos. Una vez
    que el sistema acumule ventas, el valor se podrá recalcular con el
    consumo real.
    """
    if cantidad is None or cantidad <= 0:
        return 1
    return max(1, math.ceil(cantidad * 0.15))
