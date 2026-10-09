# -*- coding: utf-8 -*-
"""
Recepción de mercancía.

Reproduce la forma en que el depósito recibe un pedido: se cotejan los
renglones de la factura uno por uno y al final se registra la entrada
completa. El costo unitario se calcula a partir del importe del
documento, incluyendo las piezas bonificadas, operación que hoy se hace
con calculadora.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import streamlit as st

import repositorio as repo
import servicios as srv
from conexion import BaseNoEncontrada

CLAVE_RECEPCION = 'recepcion_en_curso'

# Claves de los campos de captura. Se conservan en una lista para poder
# vaciarlos todos al agregar un renglón, de modo que el siguiente
# producto se capture sobre campos limpios.
CAMPOS = ('rec_producto', 'rec_cobradas', 'rec_bonificadas', 'rec_importe',
          'rec_costo', 'rec_lote', 'rec_sin_fecha', 'rec_fecha')


def limpiar_campos() -> None:
    """Vacía los campos de captura del renglón."""
    for clave in CAMPOS:
        st.session_state.pop(clave, None)


def pesos(cantidad: float) -> str:
    """Da formato de moneda a un importe."""
    return f'${cantidad:,.2f}'


def unidades(cantidad: float, singular: str, plural: str) -> str:
    """Devuelve la cantidad con su unidad en singular o plural."""
    return f'{cantidad:g} {singular if cantidad == 1 else plural}'


def renglones() -> list:
    """Devuelve los renglones de la recepción en curso."""
    if CLAVE_RECEPCION not in st.session_state:
        st.session_state[CLAVE_RECEPCION] = []
    return st.session_state[CLAVE_RECEPCION]


# ---------------------------------------------------------------------
# Captura de un renglón
# ---------------------------------------------------------------------
def formulario_renglon() -> None:
    """Agrega un producto a la recepción en curso."""
    # El selector filtra al escribir dentro de él, así que no hace falta
    # un buscador aparte.
    encontrados = repo.buscar_productos(limite=5000)
    etiquetas = {
        f'{p["clave_interna"]}  ·  {p["descripcion"]}': p['id_producto']
        for p in encontrados
    }
    # Sin selección inicial. Si viniera un producto preelegido, bastaría
    # con capturar las piezas sin mirar arriba para registrar la entrada
    # en el producto equivocado.
    elegido = st.selectbox(
        'Producto recibido', list(etiquetas), index=None,
        placeholder='Escriba parte del nombre o de la clave',
        help='Dé clic y escriba para filtrar la lista',
        key='rec_producto')
    if elegido is None:
        st.info('Elija el producto que está recibiendo.')
        return

    id_producto = etiquetas[elegido]
    producto = repo.obtener_producto(id_producto)

    pide_lote = bool(repo.consultar_una(
        'SELECT maneja_caducidad FROM producto WHERE id_producto = ?',
        (id_producto,))['maneja_caducidad'])

    columnas = st.columns(4)
    columnas[0].metric('Existencia actual', f'{producto["existencia"]:g}')
    columnas[1].metric('Costo registrado', pesos(producto['costo_unitario']))
    columnas[2].metric('Precio de venta', pesos(producto['precio_venta']))
    columnas[3].metric('Caducidad', 'Sí maneja' if pide_lote else 'No maneja')

    # Los campos van fuera de un formulario para que el costo por pieza
    # se recalcule conforme se captura, que es cuando sirve verlo.
    columnas = st.columns(2)
    cobradas = columnas[0].number_input(
        'Piezas cobradas', min_value=0.0, value=None, placeholder='0',
        help=f'Las que aparecen facturadas, en {producto["unidad_plural"]}',
        key='rec_cobradas')
    bonificadas = columnas[1].number_input(
        'Piezas bonificadas', min_value=0.0, value=None, placeholder='0',
        help='Las que el proveedor regaló y no vienen cobradas',
        key='rec_bonificadas')

    st.caption('Costo de la mercancía')
    columnas = st.columns([2, 1, 1])
    importe = columnas[0].number_input(
        'Importe de la factura por este producto ($)', min_value=0.0,
        value=None, placeholder='0.00', format='%.2f',
        help='Déjelo vacío si prefiere capturar el costo por pieza '
             'directamente',
        key='rec_importe')
    columnas[1].write('')
    con_iva = columnas[1].checkbox('El importe incluye IVA', value=True)
    costo_manual = columnas[2].number_input(
        'O costo por pieza ($)', min_value=0.0, value=None,
        placeholder='0.00', format='%.2f', key='rec_costo')

    recibidas = (cobradas or 0) + (bonificadas or 0)
    costo_calculado = None
    if importe and recibidas > 0:
        costo_calculado = srv.calcular_costo_unitario(
            importe, cobradas or 0, bonificadas or 0, con_iva)
    elif costo_manual:
        costo_calculado = costo_manual

    if recibidas > 0 and costo_calculado is not None:
        variacion = costo_calculado - producto['costo_unitario']
        columnas = st.columns(3)
        columnas[0].metric(
            'Piezas que entran',
            unidades(recibidas, producto['unidad'] if 'unidad' in producto.keys()
                     else producto['unidad_base'], producto['unidad_plural']))
        columnas[1].metric(
            'Costo por pieza', pesos(costo_calculado),
            delta=pesos(variacion) if variacion else None,
            delta_color='inverse')
        if producto['precio_venta']:
            margen = producto['precio_venta'] - costo_calculado
            columnas[2].metric(
                'Margen por pieza', pesos(margen),
                help='Diferencia entre el precio de venta registrado y el '
                     'nuevo costo')

    numero_lote = None
    fecha_caducidad = None
    if pide_lote:
        st.caption('Datos del lote, tomados del empaque o de la factura')
        columnas = st.columns(2)
        numero_lote = columnas[0].text_input(
            'Número de lote', placeholder='Déjelo vacío si no viene',
            key='rec_lote')
        sin_fecha = columnas[1].checkbox('El empaque no trae fecha',
                                         key='rec_sin_fecha')
        if not sin_fecha:
            fecha = columnas[1].date_input('Fecha de caducidad', value=None,
                                           key='rec_fecha')
            fecha_caducidad = fecha.isoformat() if fecha else None

    if st.button('Agregar a la recepción', type='primary',
                 disabled=recibidas <= 0):
        try:
            renglon = srv.preparar_recepcion(
                id_producto=id_producto,
                piezas_cobradas=cobradas or 0,
                piezas_bonificadas=bonificadas or 0,
                importe=importe,
                costo_unitario=costo_manual,
                incluye_iva=con_iva,
                numero_lote=(numero_lote or '').strip() or None,
                fecha_caducidad=fecha_caducidad,
            )
            renglones().append(renglon)
            limpiar_campos()
            st.rerun()
        except srv.ReglaDeNegocio as error:
            st.error(str(error))

    if recibidas <= 0:
        st.caption('Capture las piezas recibidas para poder agregar el renglón.')


# ---------------------------------------------------------------------
# Recepción en curso
# ---------------------------------------------------------------------
def mostrar_recepcion() -> None:
    """Lista los renglones capturados y permite confirmar la entrada."""
    pendientes = renglones()
    if not pendientes:
        st.info('Agregue los productos que vienen en la factura.')
        return

    st.subheader('Recepción en curso')

    for indice, renglon in enumerate(pendientes):
        columnas = st.columns([4, 2, 2, 1])

        detalle = unidades(renglon['recibidas'], renglon['unidad'],
                           renglon['unidad_plural'])
        if renglon['piezas_bonificadas']:
            detalle += (f'  ({renglon["piezas_cobradas"]:g} cobradas y '
                        f'{renglon["piezas_bonificadas"]:g} bonificadas)')
        columnas[0].write(f'**{renglon["descripcion"]}**')
        columnas[0].caption(detalle)

        variacion = renglon['costo_unitario'] - renglon['costo_anterior']
        columnas[1].metric(
            'Costo por pieza', pesos(renglon['costo_unitario']),
            delta=pesos(variacion) if variacion else None,
            delta_color='inverse')

        if renglon['numero_lote'] or renglon['fecha_caducidad']:
            columnas[2].caption(f'Lote {renglon["numero_lote"] or "sin número"}')
            columnas[2].caption(f'Caduca {renglon["fecha_caducidad"] or "sin fecha"}')
        elif renglon['maneja_caducidad']:
            columnas[2].caption('Sin datos de lote')

        columnas[3].write('')
        if columnas[3].button('Quitar', key=f'quitar_{indice}'):
            pendientes.pop(indice)
            st.rerun()

    st.divider()

    piezas = sum(r['recibidas'] for r in pendientes)
    importe = sum(r['importe'] or 0 for r in pendientes)

    columnas = st.columns(3)
    columnas[0].metric('Renglones', len(pendientes))
    columnas[1].metric('Piezas recibidas', f'{piezas:g}')
    columnas[2].metric('Importe capturado', pesos(importe))

    with st.form('cerrar_recepcion'):
        columnas = st.columns(2)
        referencia = columnas[0].text_input(
            'Factura o pedido', placeholder='Folio del documento')
        observaciones = columnas[1].text_input(
            'Observaciones', placeholder='Opcional')

        botones = st.columns(2)
        confirmar = botones[0].form_submit_button(
            'Registrar la recepción', type='primary')
        descartar = botones[1].form_submit_button('Descartar todo')

    if confirmar:
        try:
            resultado = srv.recibir_factura(
                pendientes,
                referencia=referencia.strip() or None,
                observaciones=observaciones.strip() or None)
            st.session_state[CLAVE_RECEPCION] = []
            st.success(
                f'Se registraron {resultado["renglones"]} renglones con '
                f'{resultado["piezas"]:g} piezas. El inventario y los costos '
                f'quedaron actualizados.')
            st.rerun()
        except srv.ReglaDeNegocio as error:
            st.error(str(error))

    if descartar:
        st.session_state[CLAVE_RECEPCION] = []
        st.rerun()


# ---------------------------------------------------------------------
st.title('Recepción de mercancía')

try:
    hay_productos = bool(repo.buscar_productos(limite=1))
except BaseNoEncontrada as error:
    st.error(str(error))
    st.stop()

if not hay_productos:
    st.warning(
        'No hay productos registrados. Dé de alta el catálogo antes de '
        'recibir mercancía.')
    st.stop()

formulario_renglon()
st.divider()
mostrar_recepcion()
