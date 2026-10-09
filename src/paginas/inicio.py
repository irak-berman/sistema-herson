# -*- coding: utf-8 -*-
"""
Pantalla de inicio del sistema.

Funciona como tablero de apertura: lo primero que el personal ve al
abrir el negocio es qué hay que pedir y qué está por caducar, en lugar
de un menú de opciones.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import streamlit as st

import repositorio as repo
from conexion import BaseNoEncontrada


def pesos(cantidad: float) -> str:
    """Da formato de moneda a un importe."""
    return f'{cantidad:,.2f} pesos'


def mostrar_indicadores(resumen: dict) -> None:
    """Dibuja la fila de indicadores principales."""
    columnas = st.columns(4)

    columnas[0].metric('Productos activos', resumen['productos_activos'])

    columnas[1].metric(
        'Por reabastecer', resumen['por_reabastecer'],
        help='Productos cuya existencia llegó o bajó de la mínima'
    )

    columnas[2].metric(
        'Próximos a caducar', resumen['por_caducar'],
        help='Lotes con existencia que vencen dentro de 180 días'
    )

    columnas[3].metric('Valor del inventario', pesos(resumen['valor_inventario']))


def mostrar_reabastecer() -> None:
    """Lista los productos que necesitan pedirse."""
    productos = repo.productos_por_reabastecer()
    if not productos:
        st.success('Ningún producto llegó a su existencia mínima.')
        return

    st.warning(f'{len(productos)} productos necesitan reabastecerse.')
    filas = [{
        'Clave': p['clave_interna'],
        'Producto': p['descripcion'],
        'Proveedor': p['proveedor'] or 'Sin asignar',
        'Existencia': p['existencia'],
        'Mínima': p['existencia_minima'],
    } for p in productos]
    st.dataframe(filas, use_container_width=True, hide_index=True)


def mostrar_caducidades() -> None:
    """Lista los lotes próximos a vencer, el más urgente primero."""
    lotes = repo.lotes_por_caducar()
    if not lotes:
        st.success('Ningún lote vence dentro de los próximos 180 días.')
        return

    st.warning(f'{len(lotes)} lotes están por caducar.')
    filas = [{
        'Clave': l['clave_interna'],
        'Producto': l['descripcion'],
        'Lote': l['numero_lote'] or 'Sin número',
        'Caduca': l['fecha_caducidad'],
        'Días restantes': l['dias_restantes'],
        'Existencia': l['existencia_lote'],
    } for l in lotes]
    st.dataframe(filas, use_container_width=True, hide_index=True)


st.title('Depósito Dental HERSON')
st.caption('Sistema de control de inventario y análisis de ventas')

try:
    resumen = repo.resumen_inventario()
except BaseNoEncontrada as error:
    st.error(str(error))
    st.stop()

mostrar_indicadores(resumen)

if resumen['agotados']:
    st.info(f'{resumen["agotados"]} productos están agotados.')

st.divider()

pendientes, caducidades = st.tabs(
    ['Productos por reabastecer', 'Lotes por caducar'])
with pendientes:
    mostrar_reabastecer()
with caducidades:
    mostrar_caducidades()
