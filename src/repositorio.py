# -*- coding: utf-8 -*-
"""
Acceso a datos del sistema de inventario.

Agrupa las consultas y escrituras contra la base de datos. La interfaz
nunca escribe SQL: llama a estas funciones. De ese modo, un cambio en el
modelo se corrige en un solo lugar y no en cada pantalla.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
from conexion import consultar, consultar_una, ejecutar

# =====================================================================
# Proveedores y categorías
# =====================================================================


def listar_proveedores(solo_activos: bool = True) -> list:
    """Devuelve los proveedores ordenados por nombre."""
    filtro = 'WHERE activo = 1' if solo_activos else ''
    return consultar(f"""
        SELECT id_proveedor, nombre, activo, observaciones
        FROM proveedor
        {filtro}
        ORDER BY nombre
    """)


def crear_proveedor(nombre: str, observaciones: str = None) -> int:
    """Registra un proveedor y devuelve su identificador."""
    return ejecutar(
        'INSERT INTO proveedor (nombre, observaciones) VALUES (?, ?)',
        (nombre.strip(), observaciones)
    )


def listar_categorias() -> list:
    """Devuelve las categorías ordenadas por nombre."""
    return consultar("""
        SELECT id_categoria, nombre, maneja_caducidad
        FROM categoria
        ORDER BY nombre
    """)


def crear_categoria(nombre: str, maneja_caducidad: bool = False) -> int:
    """Registra una categoría y devuelve su identificador."""
    return ejecutar(
        'INSERT INTO categoria (nombre, maneja_caducidad) VALUES (?, ?)',
        (nombre.strip(), 1 if maneja_caducidad else 0)
    )


# =====================================================================
# Productos
# =====================================================================


def buscar_productos(texto: str = '', id_proveedor: int = None,
                     id_categoria: int = None, solo_activos: bool = True,
                     limite: int = 100) -> list:
    """
    Busca productos por descripción o por clave y devuelve su existencia.

    La búsqueda es parcial y no distingue mayúsculas, porque en el
    mostrador se teclea una palabra suelta del nombre, no la descripción
    completa. El límite evita traer el catálogo entero en cada pulsación.
    """
    condiciones = []
    parametros = []

    if texto.strip():
        condiciones.append('(descripcion LIKE ? OR clave_interna LIKE ?)')
        patron = f'%{texto.strip()}%'
        parametros.extend([patron, patron])

    if id_proveedor is not None:
        condiciones.append('proveedor = (SELECT nombre FROM proveedor WHERE id_proveedor = ?)')
        parametros.append(id_proveedor)

    if id_categoria is not None:
        condiciones.append('categoria = (SELECT nombre FROM categoria WHERE id_categoria = ?)')
        parametros.append(id_categoria)

    if solo_activos:
        condiciones.append('activo = 1')

    filtro = 'WHERE ' + ' AND '.join(condiciones) if condiciones else ''
    parametros.append(limite)

    return consultar(f"""
        SELECT *
        FROM v_existencia
        {filtro}
        ORDER BY descripcion
        LIMIT ?
    """, tuple(parametros))


def obtener_producto(id_producto: int):
    """Devuelve un producto con su existencia actual, o None."""
    return consultar_una(
        'SELECT * FROM v_existencia WHERE id_producto = ?',
        (id_producto,)
    )


def obtener_producto_por_clave(clave_interna: str):
    """Devuelve un producto buscándolo por su clave interna, o None."""
    return consultar_una(
        'SELECT * FROM v_existencia WHERE clave_interna = ?',
        (clave_interna.strip(),)
    )


def siguiente_clave_interna(prefijo: str = 'HER') -> str:
    """
    Genera la siguiente clave interna consecutiva.

    Las claves del proveedor no sirven como identificador porque se
    repiten entre proveedores, así que el sistema asigna la suya con el
    formato PREFIJO-0001.
    """
    fila = consultar_una("""
        SELECT clave_interna
        FROM producto
        WHERE clave_interna LIKE ?
        ORDER BY LENGTH(clave_interna) DESC, clave_interna DESC
        LIMIT 1
    """, (f'{prefijo}-%',))

    if fila is None:
        return f'{prefijo}-0001'

    try:
        consecutivo = int(fila['clave_interna'].split('-')[-1]) + 1
    except (ValueError, IndexError):
        consecutivo = 1
    return f'{prefijo}-{consecutivo:04d}'


def crear_producto(descripcion: str, id_categoria: int,
                   id_proveedor: int = None, clave_proveedor: str = None,
                   unidad_base: str = 'pieza', costo_unitario: float = 0,
                   precio_venta: float = 0, existencia_minima: int = 1,
                   maneja_caducidad: bool = None,
                   clave_interna: str = None) -> int:
    """
    Da de alta un producto y devuelve su identificador.

    Si no se indica clave interna, se genera la siguiente consecutiva.
    Si no se indica el manejo de caducidad, se hereda de la categoría,
    conforme al criterio acordado con el propietario.
    """
    if clave_interna is None:
        clave_interna = siguiente_clave_interna()

    if maneja_caducidad is None:
        categoria = consultar_una(
            'SELECT maneja_caducidad FROM categoria WHERE id_categoria = ?',
            (id_categoria,)
        )
        maneja_caducidad = bool(categoria['maneja_caducidad']) if categoria else False

    return ejecutar("""
        INSERT INTO producto
            (clave_interna, clave_proveedor, descripcion, id_categoria,
             id_proveedor, unidad_base, costo_unitario, precio_venta,
             existencia_minima, maneja_caducidad)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (clave_interna, clave_proveedor, descripcion.strip(), id_categoria,
          id_proveedor, unidad_base, costo_unitario, precio_venta,
          existencia_minima, 1 if maneja_caducidad else 0))


def actualizar_producto(id_producto: int, **campos) -> None:
    """
    Modifica los campos indicados de un producto.

    Solo se aceptan campos de una lista fija, para que un error de
    escritura no termine armando una sentencia inválida.
    """
    PERMITIDOS = {
        'descripcion', 'clave_proveedor', 'id_categoria', 'id_proveedor',
        'unidad_base', 'costo_unitario', 'precio_venta',
        'existencia_minima', 'maneja_caducidad', 'activo'
    }
    cambios = {c: v for c, v in campos.items() if c in PERMITIDOS}
    if not cambios:
        return

    asignaciones = ', '.join(f'{campo} = ?' for campo in cambios)
    valores = list(cambios.values()) + [id_producto]
    ejecutar(f'UPDATE producto SET {asignaciones} WHERE id_producto = ?',
             tuple(valores))


# =====================================================================
# Presentaciones
# =====================================================================


def listar_presentaciones(id_producto: int) -> list:
    """
    Devuelve las presentaciones de un producto.

    La predeterminada aparece primero, para que la pantalla de venta la
    ofrezca sin que el usuario tenga que elegir.
    """
    return consultar("""
        SELECT id_presentacion, nombre, factor, precio_venta, es_predeterminada
        FROM presentacion
        WHERE id_producto = ?
        ORDER BY es_predeterminada DESC, factor
    """, (id_producto,))


def crear_presentacion(id_producto: int, nombre: str, factor: float,
                       precio_venta: float,
                       es_predeterminada: bool = False) -> int:
    """Registra una presentación y devuelve su identificador."""
    return ejecutar("""
        INSERT INTO presentacion
            (id_producto, nombre, factor, precio_venta, es_predeterminada)
        VALUES (?, ?, ?, ?, ?)
    """, (id_producto, nombre.strip(), factor, precio_venta,
          1 if es_predeterminada else 0))


# =====================================================================
# Consultas de apoyo
# =====================================================================


def productos_por_reabastecer() -> list:
    """Productos cuya existencia llegó o bajó de la mínima configurada."""
    return consultar('SELECT * FROM v_por_reabastecer ORDER BY descripcion')


def lotes_por_caducar() -> list:
    """Lotes con existencia que caducan dentro del plazo definido."""
    return consultar('SELECT * FROM v_caducidad_proxima')


def resumen_inventario() -> dict:
    """
    Devuelve los indicadores que se muestran en la pantalla de inicio.

    Se calculan en una sola consulta por cada uno para evitar recorrer
    el catálogo varias veces desde la interfaz.
    """
    productos = consultar_una(
        'SELECT COUNT(*) AS total FROM producto WHERE activo = 1')
    agotados = consultar_una(
        'SELECT COUNT(*) AS total FROM v_existencia WHERE existencia <= 0')
    reabastecer = consultar_una(
        'SELECT COUNT(*) AS total FROM v_por_reabastecer')
    caducidad = consultar_una(
        'SELECT COUNT(*) AS total FROM v_caducidad_proxima')
    valor = consultar_una("""
        SELECT COALESCE(SUM(existencia * costo_unitario), 0) AS total
        FROM v_existencia
        WHERE existencia > 0
    """)

    return {
        'productos_activos': productos['total'],
        'agotados': agotados['total'],
        'por_reabastecer': reabastecer['total'],
        'por_caducar': caducidad['total'],
        'valor_inventario': valor['total'],
    }
