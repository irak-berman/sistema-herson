# -*- coding: utf-8 -*-
"""
Movimientos de inventario y corrección de errores de captura.

Permite revisar lo que se registró y corregirlo. Los datos descriptivos
de un lote se corrigen directamente, porque no alteran la existencia.
Las cantidades se corrigen mediante un ajuste que queda visible en el
historial, de modo que el inventario siempre pueda explicar por qué hay
lo que hay.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
from datetime import date

import streamlit as st

import repositorio as repo
import servicios as srv
from conexion import BaseNoEncontrada

NOMBRES_TIPO = {
    'entrada': 'Entrada',
    'salida': 'Salida',
    'ajuste': 'Ajuste',
    'merma': 'Merma',
}


def pesos(cantidad: float) -> str:
    """Da formato de moneda a un importe."""
    return f'${cantidad:,.2f}'


def unidades(cantidad: float, singular: str, plural: str) -> str:
    """Devuelve la cantidad con su unidad en singular o plural."""
    return f'{cantidad:g} {singular if cantidad == 1 else plural}'


# ---------------------------------------------------------------------
# Corrección de un movimiento
# ---------------------------------------------------------------------
def tarjeta_movimiento(movimiento: dict, contexto: str) -> None:
    """
    Muestra un movimiento y ofrece corregirlo.

    Streamlit construye el contenido de todas las pestañas aunque solo
    una esté visible, por lo que un mismo movimiento puede dibujarse
    varias veces. El contexto distingue las claves de sus campos.
    """
    identificador = f'{contexto}_{movimiento["id_movimiento"]}'
    id_movimiento = movimiento['id_movimiento']
    cantidad = movimiento['cantidad']
    signo = '+' if cantidad > 0 else ''

    titulo = (f'{NOMBRES_TIPO.get(movimiento["tipo"], movimiento["tipo"])}  ·  '
              f'{movimiento["descripcion"]}  ·  {signo}{cantidad:g} '
              f'{movimiento["unidad_plural"]}  ·  '
              f'{movimiento["fecha"][:16]}')

    with st.expander(titulo):
        if movimiento['referencia']:
            st.caption(f'Documento {movimiento["referencia"]}')
        if movimiento['observaciones']:
            st.caption(movimiento['observaciones'])

        # --- Cantidad -------------------------------------------------
        st.write('**Cantidad registrada**')
        columnas = st.columns([1, 2, 1])
        correcta = columnas[0].number_input(
            'Cantidad correcta', min_value=0.0, value=abs(float(cantidad)),
            key=f'cant_{identificador}',
            help='Capture la cantidad que debió registrarse. El sistema '
                 'generará un ajuste por la diferencia.')
        motivo = columnas[1].text_input(
            'Motivo de la corrección', key=f'mot_{identificador}',
            placeholder='Por ejemplo, error de captura')
        columnas[2].write('')
        if columnas[2].button('Corregir cantidad', key=f'bc_{identificador}'):
            try:
                resultado = srv.corregir_cantidad(
                    id_movimiento, correcta, motivo.strip() or None)
                if resultado['diferencia'] == 0:
                    st.info('La cantidad capturada es la que ya estaba '
                            'registrada.')
                else:
                    st.success(
                        f'Se generó un ajuste de '
                        f'{resultado["diferencia"]:+g} '
                        f'{movimiento["unidad_plural"]}.')
                    st.rerun()
            except srv.ReglaDeNegocio as error:
                st.error(str(error))

        # --- Costo, solo en entradas ----------------------------------
        if movimiento['tipo'] == 'entrada':
            st.write('**Costo por pieza**')
            columnas = st.columns([1, 2, 1])
            costo_guardado = float(movimiento['costo_unitario'] or 0)
            costo = columnas[0].number_input(
                'Costo correcto ($)', min_value=0.0, format='%.2f',
                value=round(costo_guardado, 2),
                key=f'cos_{identificador}',
                help='Se muestra redondeado a centavos. El sistema conserva '
                     'la precisión completa mientras no lo modifique.')
            columnas[1].write('')
            actualizar = columnas[1].checkbox(
                'Actualizar también el costo vigente del producto',
                value=True, key=f'act_{identificador}')
            columnas[2].write('')
            if columnas[2].button('Corregir costo', key=f'bk_{identificador}'):
                try:
                    nuevo = (costo_guardado
                             if round(costo_guardado, 2) == costo else costo)
                    srv.corregir_costo(id_movimiento, nuevo, actualizar)
                    st.success('Costo corregido.')
                    st.rerun()
                except srv.ReglaDeNegocio as error:
                    st.error(str(error))

        # --- Lote y caducidad -----------------------------------------
        if movimiento['id_lote']:
            st.write('**Lote y caducidad**')
            st.caption(
                'Estos datos no afectan la existencia, por lo que se '
                'corrigen directamente.')
            columnas = st.columns([1, 1, 1])
            numero = columnas[0].text_input(
                'Número de lote', value=movimiento['numero_lote'] or '',
                key=f'lot_{identificador}')

            actual = movimiento['fecha_caducidad']
            sin_fecha = columnas[1].checkbox(
                'Sin fecha de caducidad', value=actual is None,
                key=f'sf_{identificador}')
            nueva_fecha = None
            if not sin_fecha:
                valor = date.fromisoformat(actual) if actual else None
                elegida = columnas[1].date_input(
                    'Fecha de caducidad', value=valor,
                    key=f'fec_{identificador}')
                nueva_fecha = elegida.isoformat() if elegida else None

            columnas[2].write('')
            if columnas[2].button('Guardar lote', key=f'bl_{identificador}'):
                repo.actualizar_lote(
                    movimiento['id_lote'],
                    numero_lote=numero,
                    fecha_caducidad=nueva_fecha if not sin_fecha else '')
                st.success('Datos del lote corregidos.')
                st.rerun()


# ---------------------------------------------------------------------
st.title('Movimientos de inventario')
st.caption(
    'Revise lo registrado y corrija errores de captura. Las correcciones '
    'de cantidad no borran el movimiento original, generan un ajuste que '
    'queda visible en el historial.')

try:
    referencias = repo.referencias_recientes()
except BaseNoEncontrada as error:
    st.error(str(error))
    st.stop()

por_documento, por_producto, todos = st.tabs(
    ['Por documento', 'Por producto', 'Últimos movimientos'])

with por_documento:
    if not referencias:
        st.info('Todavía no hay recepciones con documento registrado.')
    else:
        etiquetas = {
            f'{r["referencia"]}  ·  {r["renglones"]} renglones  ·  '
            f'{r["fecha"][:10]}': r['referencia']
            for r in referencias
        }
        elegida = st.selectbox(
            'Documento', list(etiquetas), index=None,
            placeholder='Elija la factura o el pedido que desea revisar')
        if elegida:
            for movimiento in repo.movimientos_recientes(
                    limite=200, referencia=etiquetas[elegida]):
                tarjeta_movimiento(movimiento, 'doc')

with por_producto:
    productos = repo.buscar_productos(limite=5000, solo_activos=False)
    if not productos:
        st.info('Todavía no hay productos registrados.')
    else:
        etiquetas = {
            f'{p["clave_interna"]}  ·  {p["descripcion"]}': p['id_producto']
            for p in productos
        }
        elegido = st.selectbox(
            'Producto', list(etiquetas), index=None,
            placeholder='Escriba parte del nombre o de la clave')
        if elegido:
            id_producto = etiquetas[elegido]
            producto = repo.obtener_producto(id_producto)

            columnas = st.columns(3)
            columnas[0].metric(
                'Existencia actual',
                unidades(producto['existencia'], producto['unidad_base'],
                         producto['unidad_plural']))
            columnas[1].metric('Costo', pesos(producto['costo_unitario']))
            columnas[2].metric('Precio', pesos(producto['precio_venta']))

            historial = repo.movimientos_recientes(limite=200)
            propios = [m for m in historial if m['id_producto'] == id_producto]
            if not propios:
                st.info('Este producto todavía no tiene movimientos.')
            for movimiento in propios:
                tarjeta_movimiento(movimiento, 'prod')

with todos:
    recientes = repo.movimientos_recientes(limite=50)
    if not recientes:
        st.info('Todavía no hay movimientos registrados.')
    for movimiento in recientes:
        tarjeta_movimiento(movimiento, 'ult')
