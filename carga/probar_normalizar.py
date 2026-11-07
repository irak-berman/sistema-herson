# -*- coding: utf-8 -*-
"""
Pruebas de la normalización de valores del archivo de inventario.

Los casos salen del archivo real del depósito, no de ejemplos
inventados, porque lo que hay que comprobar es que el programa entiende
la forma en que ese negocio escribe sus precios.

Uso: python carga/probar_normalizar.py

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalizar import (a_numero, existencia_minima, leer_cantidad,
                        leer_precio)

fallos = []


def comprobar(descripcion: str, obtenido, esperado) -> None:
    """Compara un resultado con lo esperado y acumula los fallos."""
    if obtenido == esperado:
        print(f'  ok    {descripcion}')
    else:
        print(f'  FALLA {descripcion}')
        print(f'        esperado {esperado!r}, obtenido {obtenido!r}')
        fallos.append(descripcion)


print('Lectura de números')
comprobar('número entero', a_numero(450), 450.0)
comprobar('número con decimales', a_numero(488.5), 488.5)
comprobar('texto con signo de pesos', a_numero('$1,234.50'), 1234.5)
comprobar('texto con espacios', a_numero('  450 '), 450.0)
comprobar('celda vacía', a_numero(None), None)
comprobar('celda en blanco', a_numero('   '), None)
comprobar('un número con ruido', a_numero('5 pzs'), 5.0)
comprobar('dos números, no se adivina', a_numero('30cmX $10'), None)
comprobar('texto sin números', a_numero('por cotizar'), None)

print()
print('Lectura de cantidades')
comprobar('cantidad normal', leer_cantidad(11), (11.0, None))
comprobar('cantidad en cero', leer_cantidad(0), (0.0, None))
comprobar('celda vacía se carga en cero',
          leer_cantidad(None)[0], 0.0)
comprobar('cantidad ilegible no se adivina',
          leer_cantidad('1c/ 0 pzs')[0], None)
comprobar('cantidad negativa se rechaza',
          leer_cantidad(-5)[0], None)

print()
print('Lectura de precios, casos reales del archivo')

p = leer_precio(450)
comprobar('precio simple, unitario', p.unitario, 450.0)
comprobar('precio simple, sin paquetes', p.paquetes, [])

p = leer_precio('$300.00 c/u o 2 X $525.00')
comprobar('c/u más paquete, unitario', p.unitario, 300.0)
comprobar('c/u más paquete, paquetes', p.paquetes, [(2, 525.0)])

p = leer_precio('$580/ 2x $1110')
comprobar('barra más paquete, unitario', p.unitario, 580.0)
comprobar('barra más paquete, paquetes', p.paquetes, [(2, 1110.0)])

p = leer_precio('$135 o 2 x $220')
comprobar('o más paquete, unitario', p.unitario, 135.0)
comprobar('o más paquete, paquetes', p.paquetes, [(2, 220.0)])

p = leer_precio('1x $340 o 2x $600')
comprobar('una pieza escrita como paquete, unitario', p.unitario, 340.0)
comprobar('una pieza escrita como paquete, paquetes', p.paquetes, [(2, 600.0)])

p = leer_precio('1 X $900.00 "O" 2 X $1700.00')
comprobar('comillas de por medio, unitario', p.unitario, 900.0)
comprobar('comillas de por medio, paquetes', p.paquetes, [(2, 1700.0)])

p = leer_precio('10 cu / 10 x 70')
comprobar('cu sin diagonal, unitario', p.unitario, 10.0)
comprobar('cu sin diagonal, paquetes', p.paquetes, [(10, 70.0)])

p = leer_precio('30cmX $10')
comprobar('medida que no es paquete, sin paquetes', p.paquetes, [])

p = leer_precio('')
comprobar('precio vacío no es interpretable', p.interpretable, False)

p = leer_precio('por cotizar')
comprobar('texto sin número no es interpretable', p.interpretable, False)

print()
print('Existencia mínima, quince por ciento redondeado hacia arriba')
comprobar('de 240', existencia_minima(240), 36)
comprobar('de 18', existencia_minima(18), 3)
comprobar('de 500', existencia_minima(500), 75)
comprobar('de 1', existencia_minima(1), 1)
comprobar('de 0 nunca baja de 1', existencia_minima(0), 1)

print()
if fallos:
    print(f'{len(fallos)} comprobaciones fallaron.')
    raise SystemExit(1)
print('Todas las comprobaciones pasaron.')
