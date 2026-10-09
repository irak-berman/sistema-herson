# -*- coding: utf-8 -*-
"""
Secciones de la pantalla de catálogo.

Agrupa las funciones que dibujan cada sección del catálogo. Las páginas
del menú lateral las invocan, de modo que la lógica viva en un solo
archivo aunque se muestre en cuatro pantallas distintas.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import streamlit as st

import repositorio as repo
import servicios as srv
from conexion import BaseNoEncontrada

def unidades(cantidad: float, singular: str, plural: str) -> str:
    """Devuelve la cantidad con su unidad en singular o plural."""
    return f'{cantidad:g} {singular if cantidad == 1 else plural}'


def pesos(cantidad: float) -> str:
    """Da formato de moneda a un importe."""
    return f'${cantidad:,.2f}'


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
def seccion_alta(proveedores: list, categorias: list,
                 unidades_activas: list) -> None:
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
        mapa_unidades = opciones(unidades_activas, 'id_unidad', 'nombre')
        unidad = columnas[2].selectbox(
            'Unidad base', list(mapa_unidades),
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
                id_unidad=mapa_unidades[unidad],
            )
            producto = repo.obtener_producto(id_producto)
            st.success(
                f'Producto registrado con la clave {producto["clave_interna"]}. '
                f'Su existencia mínima quedó en '
                f'{unidades(producto["existencia_minima"], producto["unidad_base"], producto["unidad_plural"])}.')
        except srv.ReglaDeNegocio as error:
            st.error(str(error))


# ---------------------------------------------------------------------
# Edición y presentaciones
# ---------------------------------------------------------------------
def seccion_edicion(unidades_activas: list) -> None:
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
        f'Una presentación es una forma de vender, no de almacenar. La '
        f'existencia siempre se lleva en {producto["unidad_plural"]}. Si '
        f'agrega una caja que equivale a 100, al vender una caja el sistema '
        f'cobra su precio y descuenta 100 {producto["unidad_plural"]}. No '
        f'hace falta crear una presentación para vender por '
        f'{producto["unidad_base"]}, eso ya funciona sin configurar nada.')

    presentaciones = repo.listar_presentaciones(id_producto)
    if presentaciones:
        st.caption(
            'Toque una presentación para modificar su equivalencia y su '
            'precio, o para eliminarla.')
        for p in presentaciones:
            titulo = (f'{p["nombre"]}  ·  equivale a '
                      f'{unidades(p["factor"], producto["unidad_base"], producto["unidad_plural"])}'
                      f'  ·  {pesos(p["precio_venta"])}')
            with st.expander(titulo):
                columnas = st.columns(2)
                factor_edit = columnas[0].number_input(
                    'Equivale a', min_value=0.01, value=float(p['factor']),
                    key=f'f_pres_{p["id_presentacion"]}')
                precio_edit = columnas[1].number_input(
                    'Precio', min_value=0.0, format='%.2f',
                    value=float(p['precio_venta']),
                    key=f'p_pres_{p["id_presentacion"]}')

                usos = repo.ventas_con_presentacion(p['id_presentacion'])
                st.caption(f'Usada en {usos} ventas')

                botones = st.columns(2)
                if botones[0].button(
                        'Guardar', key=f'g_pres_{p["id_presentacion"]}'):
                    repo.actualizar_presentacion(
                        p['id_presentacion'], factor=factor_edit,
                        precio_venta=precio_edit)
                    st.rerun()

                if botones[1].button(
                        'Eliminar', key=f'x_pres_{p["id_presentacion"]}',
                        disabled=usos > 0):
                    repo.eliminar_presentacion(p['id_presentacion'])
                    st.rerun()

                if usos > 0:
                    st.caption(
                        'No se puede eliminar porque ya se vendió con ella.')
    else:
        st.caption(
            f'Sin presentaciones. El producto se vende por '
            f'{producto["unidad_base"]}.')

    with st.form('alta_presentacion', clear_on_submit=True):
        mapa_unidades = opciones(unidades_activas, 'id_unidad', 'nombre')
        columnas = st.columns([2, 1, 1])
        nombre = columnas[0].selectbox('Presentación', list(mapa_unidades))
        factor = columnas[1].number_input(
            'Equivale a', min_value=0.01, value=None, placeholder='1',
            help=f'Cuántas {producto["unidad_plural"]} entrega esta '
                 f'presentación')
        precio_pres = columnas[2].number_input(
            'Precio', min_value=0.0, value=None,
            placeholder='0.00', format='%.2f')

        agregar = st.form_submit_button('Agregar presentación')

    if agregar:
        try:
            repo.crear_presentacion(
                id_producto, mapa_unidades[nombre], numero(factor, 1.0),
                numero(precio_pres))
            st.success('Presentación agregada.')
            st.rerun()
        except Exception:
            st.error('El producto ya tiene una presentación en esa unidad.')


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

                columnas = st.columns(2)
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
                    st.caption(
                        'No se puede eliminar porque tiene productos asociados.')

                # La corrección masiva solo se ofrece cuando hay productos
                # que no coinciden con la configuración de su categoría,
                # que es lo que ocurre al corregir una clasificación
                # equivocada después de haber dado de alta productos.
                desalineados = repo.productos_desalineados(
                    categoria['id_categoria'])
                if desalineados:
                    st.warning(
                        f'{desalineados} productos de esta categoría tienen '
                        f'una configuración de caducidad distinta.')
                    if st.button(
                            f'Corregir esos {desalineados} productos',
                            key=f'a_cat_{categoria["id_categoria"]}'):
                        cambiados = repo.aplicar_caducidad_de_categoria(
                            categoria['id_categoria'])
                        st.success(f'{cambiados} productos corregidos.')
                        st.rerun()
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
# Unidades de medida
# ---------------------------------------------------------------------
def bloque_unidades() -> None:
    """Alta, edición y baja de unidades de medida."""
    st.subheader('Unidades de medida')
    st.caption(
        'Son las unidades que se ofrecen al definir un producto o una '
        'presentación. Mantenerlas en una lista evita que la misma unidad '
        'se escriba de formas distintas.')

    for unidad in repo.listar_unidades(solo_activas=False):
        estado = '' if unidad['activo'] else '  ·  inactiva'
        with st.expander(f'{unidad["nombre"]}  ·  {unidad["plural"]}{estado}'):
            columnas = st.columns(2)
            singular = columnas[0].text_input(
                'Singular', value=unidad['nombre'],
                key=f'sg_uni_{unidad["id_unidad"]}')
            plural = columnas[1].text_input(
                'Plural', value=unidad['plural'],
                key=f'pl_uni_{unidad["id_unidad"]}')

            usos = repo.usos_de_unidad(unidad['id_unidad'])

            # La opción de dejar de ofrecer una unidad solo tiene sentido
            # cuando ya no puede eliminarse. Si nadie la usa, se borra y
            # listo.
            if usos > 0:
                st.caption(
                    f'En uso por {usos} productos y presentaciones, por lo '
                    f'que no puede eliminarse sin romper el historial.')
                activa = st.checkbox(
                    'Seguir ofreciéndola al capturar',
                    value=bool(unidad['activo']),
                    key=f'ac_uni_{unidad["id_unidad"]}',
                    help='Desmárquela si el depósito dejó de manejar esta '
                         'unidad. Los registros anteriores la conservan.')
            else:
                activa = True

            botones = st.columns(2)
            if botones[0].button('Guardar', key=f'g_uni_{unidad["id_unidad"]}'):
                try:
                    repo.actualizar_unidad(
                        unidad['id_unidad'], nombre=singular,
                        plural=plural, activo=activa)
                    st.rerun()
                except Exception:
                    st.error('Ya existe una unidad con ese nombre.')

            if usos == 0 and botones[1].button(
                    'Eliminar', key=f'x_uni_{unidad["id_unidad"]}'):
                repo.eliminar_unidad(unidad['id_unidad'])
                st.rerun()

    with st.form('alta_unidad', clear_on_submit=True):
        columnas = st.columns(2)
        singular = columnas[0].text_input('Nueva unidad', placeholder='ampolleta')
        plural = columnas[1].text_input('Su plural', placeholder='ampolletas')
        agregar = st.form_submit_button('Agregar unidad')

    if agregar:
        if not singular.strip() or not plural.strip():
            st.error('Se requieren el singular y el plural.')
        else:
            try:
                repo.crear_unidad(singular, plural)
                st.rerun()
            except Exception:
                st.error('Esa unidad ya existe.')


# ---------------------------------------------------------------------
# Datos de apoyo que varias secciones necesitan
# ---------------------------------------------------------------------
def cargar_catalogos() -> tuple:
    """
    Devuelve proveedores, categorías y unidades activas.

    Si la base de datos no existe, muestra el error y detiene la página,
    en lugar de dejar que falle con un mensaje técnico.
    """
    try:
        return (repo.listar_proveedores(),
                repo.listar_categorias(),
                repo.listar_unidades())
    except BaseNoEncontrada as error:
        st.error(str(error))
        st.stop()
