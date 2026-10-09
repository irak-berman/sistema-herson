# -*- coding: utf-8 -*-
"""
Pantalla de catálogo de productos.

Permite buscar, dar de alta y modificar productos, administrar sus
presentaciones y mantener los catálogos de proveedores y categorías.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import streamlit as st

import repositorio as repo
import servicios as srv
from conexion import BaseNoEncontrada

# Lista cerrada de unidades base. Evita que el mismo concepto se guarde
# escrito de formas distintas, que es uno de los problemas detectados en
# el archivo de Excel del depósito.
UNIDADES_BASE = [
    'pieza', 'caja', 'paquete', 'frasco', 'bote', 'tubo',
    'sobre', 'jeringa', 'rollo', 'par', 'juego', 'kit',
]


def pesos(cantidad: float) -> str:
    """Da formato de moneda a un importe."""
    return f'{cantidad:,.2f}'


def opciones(filas: list, campo_id: str, campo_nombre: str) -> dict:
    """Convierte una lista de filas en un diccionario para los selectores."""
    return {fila[campo_nombre]: fila[campo_id] for fila in filas}


def numero(valor, por_omision: float = 0.0) -> float:
    """Devuelve el valor capturado o el de omisión si el campo quedó vacío."""
    return por_omision if valor is None else float(valor)


# ---------------------------------------------------------------------
# Búsqueda y listado
# ---------------------------------------------------------------------
def seccion_busqueda(proveedores: list, categorias: list) -> None:
    """Buscador de productos con filtros por proveedor y categoría."""
    columnas = st.columns([3, 2, 2])

    texto = columnas[0].text_input(
        'Buscar producto', placeholder='Nombre o clave')

    mapa_proveedores = opciones(proveedores, 'id_proveedor', 'nombre')
    proveedor = columnas[1].selectbox(
        'Proveedor', ['Todos los proveedores'] + list(mapa_proveedores))

    mapa_categorias = opciones(categorias, 'id_categoria', 'nombre')
    categoria = columnas[2].selectbox(
        'Categoría', ['Todas las categorías'] + list(mapa_categorias))

    incluir_bajas = st.checkbox('Incluir productos dados de baja')

    resultados = repo.buscar_productos(
        texto=texto,
        id_proveedor=mapa_proveedores.get(proveedor),
        id_categoria=mapa_categorias.get(categoria),
        solo_activos=not incluir_bajas,
    )

    if not resultados:
        st.info('No se encontraron productos con esos criterios.')
        return

    st.caption(f'{len(resultados)} productos encontrados')
    filas = [{
        'Clave': p['clave_interna'],
        'Producto': p['descripcion'],
        'Categoría': p['categoria'] or '',
        'Proveedor': p['proveedor'] or '',
        'Existencia': p['existencia'],
        'Mínima': p['existencia_minima'],
        'Costo': pesos(p['costo_unitario']),
        'Precio': pesos(p['precio_venta']),
    } for p in resultados]
    st.dataframe(filas, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------
# Alta de producto
# ---------------------------------------------------------------------
def seccion_alta(proveedores: list, categorias: list) -> None:
    """Formulario de alta de producto con su existencia inicial."""
    if not categorias:
        st.warning(
            'Registre al menos una categoría antes de dar de alta productos.')
        return

    mapa_proveedores = opciones(proveedores, 'id_proveedor', 'nombre')
    mapa_categorias = opciones(categorias, 'id_categoria', 'nombre')

    with st.form('alta_producto', clear_on_submit=True):
        descripcion = st.text_input('Descripción del producto')

        columnas = st.columns(3)
        categoria = columnas[0].selectbox('Categoría', list(mapa_categorias))
        proveedor = columnas[1].selectbox(
            'Proveedor', ['Sin asignar'] + list(mapa_proveedores))
        unidad = columnas[2].selectbox(
            'Unidad base', UNIDADES_BASE,
            help='Unidad en la que se controla la existencia. Normalmente '
                 'la más pequeña en que se vende el producto.')

        columnas = st.columns(4)
        clave_proveedor = columnas[0].text_input(
            'Clave del proveedor', placeholder='Opcional')
        existencia = columnas[1].number_input(
            'Existencia inicial', min_value=0.0, value=None,
            placeholder='0',
            help='Cantidad en unidad base. Si la unidad es pieza y tiene 3 '
                 'cajas de 100, capture 300.')
        costo = columnas[2].number_input(
            'Costo unitario', min_value=0.0, value=None,
            placeholder='0.00', format='%.2f')
        precio = columnas[3].number_input(
            'Precio de venta', min_value=0.0, value=None,
            placeholder='0.00', format='%.2f')

        enviado = st.form_submit_button('Dar de alta', type='primary')

    if enviado:
        if not descripcion.strip():
            st.error('La descripción es obligatoria.')
            return
        try:
            cantidad = numero(existencia)
            id_producto = srv.alta_rapida(
                descripcion=descripcion,
                id_categoria=mapa_categorias[categoria],
                id_proveedor=mapa_proveedores.get(proveedor),
                existencia=cantidad,
                costo_unitario=numero(costo),
                precio_venta=numero(precio),
                clave_proveedor=clave_proveedor.strip() or None,
                unidad_base=unidad,
            )
            producto = repo.obtener_producto(id_producto)
            st.success(
                f'Producto registrado con la clave {producto["clave_interna"]}. '
                f'Su existencia mínima quedó en '
                f'{producto["existencia_minima"]} {unidad}.')
        except srv.ReglaDeNegocio as error:
            st.error(str(error))


# ---------------------------------------------------------------------
# Edición y presentaciones
# ---------------------------------------------------------------------
def seccion_edicion() -> None:
    """Permite modificar un producto y administrar sus presentaciones."""
    productos = repo.buscar_productos(limite=500, solo_activos=False)
    if not productos:
        st.info('Todavía no hay productos registrados.')
        return

    etiquetas = {
        f'{p["clave_interna"]}  ·  {p["descripcion"]}': p['id_producto']
        for p in productos
    }
    elegido = st.selectbox('Producto a editar', list(etiquetas))
    id_producto = etiquetas[elegido]
    producto = repo.obtener_producto(id_producto)

    columnas = st.columns(4)
    columnas[0].metric('Existencia', f'{producto["existencia"]:g}')
    columnas[1].metric('Mínima', producto['existencia_minima'])
    columnas[2].metric('Costo', pesos(producto['costo_unitario']))
    columnas[3].metric('Precio', pesos(producto['precio_venta']))

    with st.form('editar_producto'):
        descripcion = st.text_input('Descripción', value=producto['descripcion'])

        columnas = st.columns(4)
        costo = columnas[0].number_input(
            'Costo unitario', min_value=0.0, format='%.2f',
            value=float(producto['costo_unitario']))
        precio = columnas[1].number_input(
            'Precio de venta', min_value=0.0, format='%.2f',
            value=float(producto['precio_venta']))
        minima = columnas[2].number_input(
            'Existencia mínima', min_value=0, step=1,
            value=int(producto['existencia_minima']))
        columnas[3].write('')
        activo = columnas[3].checkbox('Producto activo',
                                      value=bool(producto['activo']))

        guardar = st.form_submit_button('Guardar cambios', type='primary')

    if guardar:
        repo.actualizar_producto(
            id_producto,
            descripcion=descripcion.strip(),
            costo_unitario=costo,
            precio_venta=precio,
            existencia_minima=minima,
            activo=1 if activo else 0,
        )
        st.success('Cambios guardados.')
        st.rerun()

    st.divider()
    st.subheader('Presentaciones')
    st.caption(
        f'Cada presentación indica cuántas unidades base entrega. Una caja '
        f'con factor 100 descuenta 100 {producto["unidad_base"]} al venderse.')

    presentaciones = repo.listar_presentaciones(id_producto)
    if presentaciones:
        filas = [{
            'Presentación': p['nombre'],
            'Equivale a': f'{p["factor"]:g} {producto["unidad_base"]}',
            'Precio': pesos(p['precio_venta']),
            'Predeterminada': 'Sí' if p['es_predeterminada'] else '',
        } for p in presentaciones]
        st.dataframe(filas, use_container_width=True, hide_index=True)
    else:
        st.caption(
            f'Sin presentaciones. El producto se venderá por '
            f'{producto["unidad_base"]}.')

    with st.form('alta_presentacion', clear_on_submit=True):
        columnas = st.columns([2, 1, 1, 1])
        nombre = columnas[0].selectbox('Presentación', UNIDADES_BASE)
        factor = columnas[1].number_input(
            'Equivale a', min_value=0.01, value=None, placeholder='1',
            help=f'Cuántas {producto["unidad_base"]} entrega esta presentación')
        precio_pres = columnas[2].number_input(
            'Precio', min_value=0.0, value=None,
            placeholder='0.00', format='%.2f')
        columnas[3].write('')
        predeterminada = columnas[3].checkbox('Usar por omisión')

        agregar = st.form_submit_button('Agregar presentación')

    if agregar:
        try:
            repo.crear_presentacion(
                id_producto, nombre, numero(factor, 1.0),
                numero(precio_pres), predeterminada)
            st.success('Presentación agregada.')
            st.rerun()
        except Exception:
            st.error('Ese nombre de presentación ya existe para el producto.')


# ---------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------
def bloque_proveedores() -> None:
    """Alta, edición y baja de proveedores."""
    st.subheader('Proveedores')
    proveedores = repo.listar_proveedores(solo_activos=False)

    if proveedores:
        for proveedor in proveedores:
            estado = '' if proveedor['activo'] else '  (inactivo)'
            with st.expander(f'{proveedor["nombre"]}{estado}'):
                nombre = st.text_input(
                    'Nombre', value=proveedor['nombre'],
                    key=f'nom_prov_{proveedor["id_proveedor"]}')
                activo = st.checkbox(
                    'Activo', value=bool(proveedor['activo']),
                    key=f'act_prov_{proveedor["id_proveedor"]}')

                asociados = repo.productos_de_proveedor(proveedor['id_proveedor'])
                st.caption(f'{asociados} productos asociados')

                columnas = st.columns(2)
                if columnas[0].button(
                        'Guardar', key=f'g_prov_{proveedor["id_proveedor"]}'):
                    try:
                        repo.actualizar_proveedor(
                            proveedor['id_proveedor'], nombre=nombre, activo=activo)
                        st.rerun()
                    except Exception:
                        st.error('Ya existe un proveedor con ese nombre.')

                if columnas[1].button(
                        'Eliminar', key=f'e_prov_{proveedor["id_proveedor"]}',
                        disabled=asociados > 0):
                    repo.eliminar_proveedor(proveedor['id_proveedor'])
                    st.rerun()

                if asociados > 0:
                    st.caption(
                        'No se puede eliminar porque tiene productos. '
                        'Desactívelo si ya no le compra.')
    else:
        st.caption('Todavía no hay proveedores registrados.')

    with st.form('alta_proveedor', clear_on_submit=True):
        nombre = st.text_input('Nuevo proveedor')
        agregar = st.form_submit_button('Agregar proveedor')

    if agregar and nombre.strip():
        try:
            repo.crear_proveedor(nombre)
            st.rerun()
        except Exception:
            st.error('Ese proveedor ya existe.')


# ---------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------
def bloque_categorias() -> None:
    """Alta, edición y baja de categorías."""
    st.subheader('Categorías')

    categorias = repo.listar_categorias()

    if categorias:
        for categoria in categorias:
            marca = '  ·  caduca' if categoria['maneja_caducidad'] else ''
            with st.expander(f'{categoria["nombre"]}{marca}'):
                nombre = st.text_input(
                    'Nombre', value=categoria['nombre'],
                    key=f'nom_cat_{categoria["id_categoria"]}')
                caduca = st.checkbox(
                    'Los productos de esta categoría caducan',
                    value=bool(categoria['maneja_caducidad']),
                    key=f'cad_cat_{categoria["id_categoria"]}')

                asociados = repo.productos_de_categoria(categoria['id_categoria'])
                st.caption(f'{asociados} productos asociados')

                columnas = st.columns(3)
                if columnas[0].button(
                        'Guardar', key=f'g_cat_{categoria["id_categoria"]}'):
                    try:
                        repo.actualizar_categoria(
                            categoria['id_categoria'], nombre=nombre,
                            maneja_caducidad=caduca)
                        st.rerun()
                    except Exception:
                        st.error('Ya existe una categoría con ese nombre.')

                if columnas[1].button(
                        'Eliminar', key=f'e_cat_{categoria["id_categoria"]}',
                        disabled=asociados > 0):
                    repo.eliminar_categoria(categoria['id_categoria'])
                    st.rerun()

                if asociados > 0:
                    if columnas[2].button(
                            'Aplicar a sus productos',
                            key=f'a_cat_{categoria["id_categoria"]}',
                            help='Copia el indicador de caducidad de la '
                                 'categoría a todos sus productos'):
                        cambiados = repo.aplicar_caducidad_de_categoria(
                            categoria['id_categoria'])
                        st.success(f'{cambiados} productos actualizados.')
                    st.caption(
                        'No se puede eliminar porque tiene productos asociados.')
    else:
        st.caption('Todavía no hay categorías registradas.')

    with st.form('alta_categoria', clear_on_submit=True):
        nombre = st.text_input('Nueva categoría')
        caduca = st.checkbox('Los productos de esta categoría caducan')
        agregar = st.form_submit_button('Agregar categoría')

    if agregar and nombre.strip():
        try:
            repo.crear_categoria(nombre, caduca)
            st.rerun()
        except Exception:
            st.error('Esa categoría ya existe.')


# ---------------------------------------------------------------------
st.title('Catálogo de productos')

try:
    proveedores = repo.listar_proveedores()
    categorias = repo.listar_categorias()
except BaseNoEncontrada as error:
    st.error(str(error))
    st.stop()

buscar, alta, editar, catalogos = st.tabs(
    ['Buscar', 'Dar de alta', 'Editar', 'Proveedores y categorías'])

with buscar:
    seccion_busqueda(proveedores, categorias)
with alta:
    seccion_alta(proveedores, categorias)
with editar:
    seccion_edicion()
with catalogos:
    columna_izquierda, columna_derecha = st.columns(2)
    with columna_izquierda:
        bloque_proveedores()
    with columna_derecha:
        bloque_categorias()
