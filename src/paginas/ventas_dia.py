# -*- coding: utf-8 -*-
"""
Corte del día y recuperación de notas.

Sirve para dos cosas distintas que conviene tener juntas.

La primera es cuadrar la caja al cerrar. Cuántas notas se hicieron,
cuánto entró y en qué forma de pago, que es lo que hoy se cuenta
revisando el talonario hoja por hoja.

La segunda es volver a generar una nota ya entregada. El cliente pierde
el archivo, lo borra del teléfono o pide que se lo manden a otro número,
y sin esta pantalla la nota solo se podría descargar en los segundos
siguientes a registrarla.

Las notas no se guardan en disco. Se arman de nuevo a partir de la base
cada vez que se piden, así que una nota recuperada seis meses después
sale idéntica a la original.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
from datetime import date

import streamlit as st

import nota_pdf
import repositorio as repo
from catalogo_vistas import pesos

FORMAS = {'efectivo': 'Efectivo',
          'transferencia': 'Transferencia',
          'credito': 'Crédito'}


def resumen(ventas: list) -> None:
    """Cuántas notas, cuánto entró y por qué medio."""
    total = round(sum(v['total'] for v in ventas), 2)
    por_forma = {}
    for venta in ventas:
        por_forma[venta['forma_pago']] = round(
            por_forma.get(venta['forma_pago'], 0) + venta['total'], 2)

    columnas = st.columns(4)
    columnas[0].metric('Notas', len(ventas))
    columnas[1].metric('Total del día', pesos(total))

    # El efectivo se separa porque es el único que se cuenta a mano al
    # cerrar. Lo demás se verifica contra el estado de cuenta.
    columnas[2].metric('Efectivo', pesos(por_forma.get('efectivo', 0)))

    pendiente = round(sum(v['total'] for v in ventas
                          if v['forma_pago'] == 'credito'), 2)
    columnas[3].metric('A crédito', pesos(pendiente))


def renglon(venta) -> None:
    """Una nota del día, con su botón para recuperarla."""
    columnas = st.columns([2, 2, 4, 2, 2, 2])

    columnas[0].write(f'**{venta["folio"]}**')
    columnas[1].write(venta['fecha'][11:16])
    columnas[2].write((venta['cliente'] or '').strip() or 'Público en general')
    columnas[3].write(FORMAS.get(venta['forma_pago'], venta['forma_pago']))
    columnas[4].write(f'**{pesos(venta["total"])}**')
    columnas[4].caption(f'{venta["renglones"]} renglones')

    # La nota se arma solo si se pide. Generarlas todas al abrir la
    # pantalla sería trabajo perdido en un día de cuarenta ventas.
    with columnas[5]:
        if st.button('Nota', icon=':material/picture_as_pdf:',
                     help='Volver a generar la nota en PDF',
                     key=f'dia_pedir_{venta["id_venta"]}'):
            st.session_state[f'dia_pdf_{venta["id_venta"]}'] = True

        if st.session_state.get(f'dia_pdf_{venta["id_venta"]}'):
            try:
                documento = nota_pdf.generar(venta['id_venta'])
                st.download_button(
                    'Descargar', data=documento,
                    file_name=nota_pdf.nombre_de_archivo(venta['folio']),
                    mime='application/pdf', type='primary',
                    key=f'dia_bajar_{venta["id_venta"]}')
            except Exception as error:
                st.error(str(error))


st.title('Corte del día')

dia = st.date_input('Día', value=date.today(), format='DD/MM/YYYY',
                    key='dia_fecha')
ventas = repo.ventas_del_dia(dia.isoformat())

if not ventas:
    st.info('No hay ventas registradas ese día.')
else:
    resumen(ventas)
    st.divider()

    encabezado = st.columns([2, 2, 4, 2, 2, 2])
    for columna, titulo in zip(encabezado,
                               ('Folio', 'Hora', 'Cliente', 'Pago',
                                'Total', '')):
        columna.caption(titulo)

    for venta in ventas:
        st.divider()
        renglon(venta)

    st.divider()
    st.caption('Las notas canceladas no aparecen en este corte ni suman '
               'al total del día.')
