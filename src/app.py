# -*- coding: utf-8 -*-
"""
Punto de entrada del sistema de inventario del Depósito Dental HERSON.

Arranca la interfaz y muestra la pantalla de inicio con los indicadores
que el personal necesita ver al abrir el negocio.

Uso desde la carpeta del proyecto, con el entorno activado:
    streamlit run src/app.py

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import sys
from pathlib import Path

import streamlit as st

# Streamlit ejecuta el archivo desde la raíz del proyecto, así que la
# carpeta src debe agregarse a la ruta de búsqueda para poder importar
# los módulos propios.
CARPETA_SRC = Path(__file__).resolve().parent
if str(CARPETA_SRC) not in sys.path:
    sys.path.insert(0, str(CARPETA_SRC))

import repositorio as repo              # noqa: E402
from conexion import BaseNoEncontrada   # noqa: E402

st.set_page_config(
    page_title='Depósito Dental HERSON',
    page_icon='🦷',
    layout='wide',
)


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


def main() -> None:
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


if __name__ == '__main__':
    main()
