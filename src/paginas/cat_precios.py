# -*- coding: utf-8 -*-
"""
Revisión de cambios de precio y de costo.

La regla acordada con el propietario es que al vender no se altera el
precio, solo se concede descuento, porque el descuento se nota. Esta
pantalla es la otra mitad de esa regla: hace visible cualquier cambio
hecho en el catálogo, que de otro modo no dejaría huella.

No permite deshacer nada. Es una pantalla de consulta, igual que el
historial de movimientos, porque el registro de lo que pasó no se
corrige: se consulta.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import streamlit as st

import repositorio as repo
from catalogo_vistas import pesos

NOMBRES = {'precio_venta': 'Precio de venta',
           'costo_unitario': 'Costo'}


def renglon(cambio) -> None:
    """Dibuja un cambio del historial."""
    columnas = st.columns([4, 2, 2, 2, 2])

    columnas[0].write(f'**{cambio["descripcion"]}**')
    etiqueta = NOMBRES.get(cambio['campo'], cambio['campo'])
    if cambio['presentacion']:
        etiqueta = f'{etiqueta} de la presentación {cambio["presentacion"]}'
    columnas[0].caption(f'{cambio["clave_interna"]}  ·  {etiqueta}')

    anterior = cambio['valor_anterior']
    columnas[1].write(pesos(anterior) if anterior is not None else 'sin valor')
    columnas[2].write(f'**{pesos(cambio["valor_nuevo"])}**')

    # La diferencia se muestra con su signo, que es lo que se busca al
    # revisar: si el precio subió o bajó.
    diferencia = cambio['diferencia']
    signo = '+' if diferencia > 0 else '−'
    columnas[3].write(f'{signo} {pesos(abs(diferencia))}')

    columnas[4].write(cambio['usuario'])
    columnas[4].caption(cambio['fecha'][:16])

    if cambio['motivo']:
        st.caption(f'Motivo: {cambio["motivo"]}')


st.title('Cambios de precio')
st.caption('Todo movimiento de precio o de costo queda registrado aquí, '
           'con quién lo hizo y cuándo.')

cambios = repo.cambios_de_precio_recientes(limite=200)

if not cambios:
    st.info('Todavía no se ha modificado ningún precio ni costo.')
else:
    solo_precios = st.checkbox(
        'Ver solo precios de venta, sin los costos',
        help='Los costos cambian solos al recibir mercancía, así que '
             'suelen ser los más numerosos.')

    if solo_precios:
        cambios = [c for c in cambios if c['campo'] == 'precio_venta']

    if not cambios:
        st.info('No hay cambios de precio de venta registrados.')
    else:
        st.caption(f'{len(cambios)} cambios, del más reciente al más antiguo.')
        encabezado = st.columns([4, 2, 2, 2, 2])
        for columna, titulo in zip(encabezado,
                                   ('Producto', 'Antes', 'Después',
                                    'Diferencia', 'Quién')):
            columna.caption(titulo)

        for cambio in cambios:
            st.divider()
            renglon(cambio)
