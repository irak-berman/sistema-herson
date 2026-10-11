# -*- coding: utf-8 -*-
"""
Registro de ventas.

Es la pantalla que más se usa y la única que compite contra algo que ya
funciona: el talonario de notas a mano. Si capturar una venta aquí tarda
más que escribirla, el depósito vuelve al papel y el sistema se queda
sin datos. Por eso todo está armado alrededor de agregar un renglón en
pocos movimientos y dejar el cursor listo para el siguiente.

Tres reglas del negocio se aplican aquí.

El precio no se captura, sale del catálogo. Quien atiende el mostrador
no lo modifica.

El descuento sí se puede conceder, por renglón o sobre el total de la
nota, y queda escrito. Es la diferencia que pidió el propietario: una
rebaja se ve, un precio alterado no.

La falta de existencia avisa pero no detiene. Mientras el sistema
conviva con el registro manual puede ir desfasado del anaquel, y no
tiene caso impedir una venta que el cliente ya se está llevando.

Nota sobre el cierre de la nota. Los campos del cobro no van dentro de
un formulario a propósito. En un formulario, pulsar Enter en cualquier
campo equivale a oprimir el primer botón, que aquí sería registrar la
venta, y la nota se guardaría a media captura. Registrar una venta mueve
inventario y folio, así que debe requerir un clic deliberado y nada más.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import streamlit as st

import nota_pdf
import repositorio as repo
import servicios as srv
from catalogo_vistas import pesos

CLAVE_NOTA = 'vta_renglones'
CLAVE_ULTIMA = 'vta_ultima'
CLAVE_CICLO = 'vta_ciclo'
CLAVE_CICLO_COBRO = 'vta_ciclo_cobro'


# ---------------------------------------------------------------------
# Estado de la nota en curso
#
# Los campos se vacían cambiándoles la clave, no borrándola del estado.
# Borrar la clave de un control deja a Streamlit mostrando el valor
# anterior aunque por dentro ya esté vacío, y entonces la pantalla dice
# que no hay producto elegido mientras el cuadro sigue enseñando el
# último. Con una clave nueva, el control se construye desde cero y no
# arrastra nada.
# ---------------------------------------------------------------------
def nota() -> list:
    """Los renglones capturados que todavía no se registran."""
    if CLAVE_NOTA not in st.session_state:
        st.session_state[CLAVE_NOTA] = []
    return st.session_state[CLAVE_NOTA]


def ciclo(clave: str) -> int:
    """Número de la tanda actual de controles."""
    if clave not in st.session_state:
        st.session_state[clave] = 0
    return st.session_state[clave]


def renovar(clave: str, campos: tuple) -> None:
    """Descarta los controles de la tanda actual y abre una nueva."""
    actual = ciclo(clave)
    for campo in campos:
        st.session_state.pop(f'{campo}_{actual}', None)
    st.session_state[clave] = actual + 1


def renovar_renglon() -> None:
    """Deja los campos del producto listos para el siguiente."""
    renovar(CLAVE_CICLO,
            ('vta_producto', 'vta_presentacion', 'vta_cantidad',
             'vta_descuento'))


def renovar_cobro() -> None:
    """Deja los campos del cobro en blanco."""
    renovar(CLAVE_CICLO_COBRO,
            ('vta_forma', 'vta_cliente', 'vta_desc_total', 'vta_factura',
             'vta_obs'))


def vaciar_nota() -> None:
    """Descarta la nota en curso."""
    st.session_state[CLAVE_NOTA] = []
    renovar_renglon()
    renovar_cobro()


# ---------------------------------------------------------------------
# Captura de un renglón
# ---------------------------------------------------------------------
def formulario_renglon() -> None:
    """Agrega un producto a la nota en curso."""
    productos = repo.buscar_productos(limite=5000)
    if not productos:
        st.warning('Todavía no hay productos en el catálogo.')
        return

    etiquetas = {
        f'{p["clave_interna"]}  ·  {p["descripcion"]}': p['id_producto']
        for p in productos
    }

    tanda = ciclo(CLAVE_CICLO)

    # Sin selección inicial, por la misma razón que en recepción: un
    # producto preelegido se vende por error sin que nadie lo note.
    elegido = st.selectbox(
        'Producto', list(etiquetas), index=None,
        placeholder='Escriba parte del nombre o de la clave',
        help='Dé clic y escriba para filtrar la lista',
        key=f'vta_producto_{tanda}')

    if elegido is None:
        st.info('Elija el producto que está vendiendo.')
        return

    id_producto = etiquetas[elegido]
    producto = repo.obtener_producto(id_producto)
    presentaciones = repo.listar_presentaciones(id_producto)

    # La unidad base siempre se puede vender, exista o no una
    # presentación dada de alta.
    opciones = {f'Por {producto["unidad_base"]}': None}
    for p in presentaciones:
        opciones[f'{p["nombre"]} ({p["factor"]:g} '
                 f'{producto["unidad_plural"]})'] = p['id_presentacion']

    # Si el propietario marcó una presentación para ofrecer primero, es
    # la que aparece elegida.
    indice = 0
    for posicion, p in enumerate(presentaciones, start=1):
        if p['es_predeterminada']:
            indice = posicion
            break

    columnas = st.columns([3, 1, 1])
    etiqueta_pres = columnas[0].selectbox(
        'Presentación', list(opciones), index=indice,
        key=f'vta_presentacion_{tanda}')
    id_presentacion = opciones[etiqueta_pres]

    cantidad = columnas[1].number_input(
        'Cantidad', min_value=0.0, step=1.0, value=None, placeholder='0',
        key=f'vta_cantidad_{tanda}')
    descuento = columnas[2].number_input(
        'Descuento', min_value=0.0, step=1.0, value=None, placeholder='0',
        help='Rebaja en pesos sobre este renglón. Déjelo vacío si no hay.',
        key=f'vta_descuento_{tanda}')

    # La vista previa se calcula antes de agregar, para que quien cobra
    # vea el importe mientras teclea y no después.
    try:
        previa = srv.preparar_renglon(
            id_producto, cantidad or 0, id_presentacion, descuento or 0)
    except srv.ReglaDeNegocio:
        previa = None

    datos = st.columns(4)
    datos[0].metric('Existencia', f'{producto["existencia"]:g} '
                                  f'{producto["unidad_plural"]}')
    datos[1].metric('Precio', pesos(previa['precio_unitario']) if previa
                    else pesos(producto['precio_venta']))
    datos[2].metric('Descuento', pesos(previa['descuento']) if previa
                    else pesos(0))
    datos[3].metric('Importe', pesos(previa['importe']) if previa
                    else pesos(0))

    if cantidad and previa and previa['cantidad_base'] > producto['existencia']:
        st.warning(
            f'Se están vendiendo {previa["cantidad_base"]:g} '
            f'{producto["unidad_plural"]} y hay {producto["existencia"]:g}. '
            f'Se puede continuar, pero conviene revisar el anaquel.')

    if st.button('Agregar a la nota', type='primary',
                 disabled=not cantidad, key=f'vta_agregar_{tanda}'):
        try:
            renglon = srv.preparar_renglon(
                id_producto, cantidad, id_presentacion, descuento or 0)
        except srv.ReglaDeNegocio as error:
            st.error(str(error))
            return

        nota().append(renglon)
        # El aviso de la venta anterior estorba en cuanto se empieza
        # otra, así que se retira solo.
        st.session_state.pop(CLAVE_ULTIMA, None)
        renovar_renglon()
        st.rerun()


# ---------------------------------------------------------------------
# La nota en curso
# ---------------------------------------------------------------------
def tabla_nota() -> float:
    """Muestra los renglones capturados y devuelve el total."""
    renglones = nota()
    st.subheader('Nota en curso')

    if not renglones:
        st.caption('Sin renglones todavía.')
        return 0.0

    encabezado = st.columns([4, 2, 2, 2, 1])
    for columna, titulo in zip(encabezado,
                               ('Producto', 'Cantidad', 'Descuento',
                                'Importe', '')):
        columna.caption(titulo)

    for posicion, renglon in enumerate(renglones):
        columnas = st.columns([4, 2, 2, 2, 1])
        columnas[0].write(f'**{renglon["descripcion"]}**')
        columnas[0].caption(renglon['clave_interna'])
        columnas[1].write(f'{renglon["cantidad"]:g} × '
                          f'{renglon["presentacion"]}')
        columnas[1].caption(f'{pesos(renglon["precio_unitario"])} c/u')
        columnas[2].write(pesos(renglon['descuento'])
                          if renglon['descuento'] else '—')
        columnas[3].write(f'**{pesos(renglon["importe"])}**')

        # Botón de solo icono. La palabra no cabe en una columna
        # angosta y se cortaba. El color rojo se aplica desde app.py,
        # donde vive el resto de la apariencia.
        if columnas[4].button('', icon=':material/delete:',
                              help='Quitar este renglón',
                              key=f'vta_quitar_{posicion}'):
            renglones.pop(posicion)
            st.rerun()

    bruto = round(sum(r['importe_bruto'] for r in renglones), 2)
    rebajas = round(sum(r['descuento'] for r in renglones), 2)
    total = round(bruto - rebajas, 2)

    st.divider()
    totales = st.columns([6, 2])
    if rebajas:
        totales[0].write('Importe sin descuento')
        totales[1].write(pesos(bruto))
        totales[0].write('Descuento de los renglones')
        totales[1].write(f'− {pesos(rebajas)}')
    totales[0].write('**Total**')
    totales[1].write(f'**{pesos(total)}**')

    return total


# ---------------------------------------------------------------------
# Cierre de la nota
# ---------------------------------------------------------------------
def cierre_de_nota() -> None:
    """Pide los datos del cobro y registra la venta."""
    tanda = ciclo(CLAVE_CICLO_COBRO)

    columnas = st.columns(2)
    forma = columnas[0].selectbox(
        'Forma de pago', ('efectivo', 'transferencia', 'credito'),
        key=f'vta_forma_{tanda}')
    cliente = columnas[1].text_input(
        'Cliente', placeholder='Solo si hay crédito o factura',
        key=f'vta_cliente_{tanda}')

    columnas = st.columns(2)
    descuento_total = columnas[0].number_input(
        'Descuento sobre el total', min_value=0.0, step=10.0,
        value=None, placeholder='0',
        help='Para dejar la nota en un número redondo. Se reparte '
             'entre los renglones en proporción a su importe.',
        key=f'vta_desc_total_{tanda}')
    factura = columnas[1].checkbox('Requiere factura',
                                   key=f'vta_factura_{tanda}')

    observaciones = st.text_input('Observaciones', placeholder='Opcional',
                                  key=f'vta_obs_{tanda}')

    if forma == 'credito' and not cliente.strip():
        st.warning('Una venta a crédito necesita el nombre del cliente.')

    st.caption('La venta se registra solo con este botón. Pulsar Enter en '
               'los campos de arriba no la guarda.')

    botones = st.columns([2, 2, 4])
    registrar = botones[0].button('Registrar venta', type='primary',
                                  key=f'vta_registrar_{tanda}')
    descartar = botones[1].button('Descartar nota',
                                  key=f'vta_descartar_{tanda}')

    if descartar:
        vaciar_nota()
        st.rerun()

    if not registrar:
        return

    try:
        resultado = srv.registrar_venta(
            nota(), forma_pago=forma, cliente=cliente,
            descuento=descuento_total or 0,
            requiere_factura=factura,
            observaciones=observaciones or None)
    except srv.ReglaDeNegocio as error:
        st.error(str(error))
        return

    # La nota se vacía solo después de que la venta quedó guardada.
    st.session_state[CLAVE_ULTIMA] = resultado
    vaciar_nota()
    st.rerun()


def aviso_de_ultima_venta() -> None:
    """
    Confirma la venta recién registrada y permite deshacerla.

    El botón de cancelar vive aquí porque es el momento en que se nota
    el error: la nota acaba de salir y el cliente sigue enfrente.
    Cancelar no borra la venta, registra los movimientos que devuelven
    la mercancía al inventario, de modo que quede el rastro de que hubo
    una venta y de que se canceló.
    """
    ultima = st.session_state.get(CLAVE_ULTIMA)
    if not ultima:
        return

    with st.container(border=True):
        st.markdown(f'### Venta registrada, folio {ultima["folio"]}')
        st.markdown(f'Total cobrado **{pesos(ultima["total"])}**')

        botones = st.columns([2, 2, 2, 3])

        # La nota se arma aquí mismo, que es cuando hace falta: el
        # cliente sigue enfrente esperando su comprobante. Si fallara,
        # la venta ya quedó registrada, así que el error se avisa sin
        # tumbar el resto de la pantalla.
        try:
            documento = nota_pdf.generar(ultima['id_venta'])
            botones[0].download_button(
                'Descargar nota', data=documento,
                file_name=nota_pdf.nombre_de_archivo(ultima['folio']),
                mime='application/pdf', type='primary',
                key='vta_descargar')
        except Exception as error:
            botones[0].error(f'No se pudo armar la nota: {error}')

        if botones[1].button('Nueva venta', key='vta_nueva'):
            st.session_state.pop(CLAVE_ULTIMA, None)
            st.rerun()

        if botones[2].button('Cancelar esta venta', key='vta_cancelar'):
            try:
                srv.cancelar_venta(
                    ultima['id_venta'],
                    motivo='Cancelada desde la pantalla de venta')
            except srv.ReglaDeNegocio as error:
                st.error(str(error))
                return
            st.session_state.pop(CLAVE_ULTIMA, None)
            st.warning(f'La venta {ultima["folio"]} se canceló y la '
                       f'mercancía regresó al inventario.')
            st.rerun()


# ---------------------------------------------------------------------
# Pantalla
# ---------------------------------------------------------------------
st.title('Registrar venta')

aviso_de_ultima_venta()
formulario_renglon()
st.divider()
tabla_nota()

if nota():
    st.divider()
    cierre_de_nota()
