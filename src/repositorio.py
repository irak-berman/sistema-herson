# -*- coding: utf-8 -*-
"""
Acceso a datos del sistema de inventario.

Agrupa las consultas y escrituras contra la base de datos. La interfaz
nunca escribe SQL: llama a estas funciones. De ese modo, un cambio en el
modelo se corrige en un solo lugar y no en cada pantalla.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
from conexion import conexion_abierta, consultar, consultar_una, ejecutar

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
# Unidades de medida
# =====================================================================


def listar_unidades(solo_activas: bool = True) -> list:
    """Devuelve las unidades de medida ordenadas por nombre."""
    filtro = 'WHERE activo = 1' if solo_activas else ''
    return consultar(f"""
        SELECT id_unidad, nombre, plural, activo
        FROM unidad
        {filtro}
        ORDER BY nombre
    """)


def crear_unidad(nombre: str, plural: str) -> int:
    """Registra una unidad de medida y devuelve su identificador."""
    return ejecutar(
        'INSERT INTO unidad (nombre, plural) VALUES (?, ?)',
        (nombre.strip().lower(), plural.strip().lower())
    )


def actualizar_unidad(id_unidad: int, nombre: str = None, plural: str = None,
                      activo: bool = None) -> None:
    """Modifica una unidad de medida."""
    cambios = {}
    if nombre is not None:
        cambios['nombre'] = nombre.strip().lower()
    if plural is not None:
        cambios['plural'] = plural.strip().lower()
    if activo is not None:
        cambios['activo'] = 1 if activo else 0
    if not cambios:
        return

    asignaciones = ', '.join(f'{campo} = ?' for campo in cambios)
    ejecutar(f'UPDATE unidad SET {asignaciones} WHERE id_unidad = ?',
             tuple(list(cambios.values()) + [id_unidad]))


def usos_de_unidad(id_unidad: int) -> int:
    """Cuenta productos y presentaciones que usan una unidad."""
    fila = consultar_una("""
        SELECT
            (SELECT COUNT(*) FROM producto WHERE id_unidad = ?) +
            (SELECT COUNT(*) FROM presentacion WHERE id_unidad = ?) AS total
    """, (id_unidad, id_unidad))
    return fila['total']


def eliminar_unidad(id_unidad: int) -> None:
    """
    Elimina una unidad que no esté en uso.

    Si ya hay productos o presentaciones que la usan, no se borra: se
    desactiva, de modo que deje de ofrecerse sin romper lo registrado.
    """
    if usos_de_unidad(id_unidad) > 0:
        raise ValueError(
            'La unidad está en uso. Se puede desactivar, pero no eliminar.')
    ejecutar('DELETE FROM unidad WHERE id_unidad = ?', (id_unidad,))


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


def crear_producto(descripcion: str, id_categoria: int, id_unidad: int,
                   id_proveedor: int = None, clave_proveedor: str = None,
                   costo_unitario: float = 0,
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
             id_proveedor, id_unidad, costo_unitario, precio_venta,
             existencia_minima, maneja_caducidad)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (clave_interna, clave_proveedor, descripcion.strip(), id_categoria,
          id_proveedor, id_unidad, costo_unitario, precio_venta,
          existencia_minima, 1 if maneja_caducidad else 0))


def actualizar_producto(id_producto: int, **campos) -> None:
    """
    Modifica los campos indicados de un producto.

    Solo se aceptan campos de una lista fija, para que un error de
    escritura no termine armando una sentencia inválida.
    """
    PERMITIDOS = {
        'descripcion', 'clave_proveedor', 'id_categoria', 'id_proveedor',
        'id_unidad', 'costo_unitario', 'precio_venta',
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
        SELECT
            p.id_presentacion,
            p.id_unidad,
            u.nombre  AS nombre,
            u.plural  AS plural,
            p.factor,
            p.precio_venta,
            p.es_predeterminada
        FROM presentacion p
        JOIN unidad u ON u.id_unidad = p.id_unidad
        WHERE p.id_producto = ?
        ORDER BY p.es_predeterminada DESC, p.factor
    """, (id_producto,))


def crear_presentacion(id_producto: int, id_unidad: int, factor: float,
                       precio_venta: float,
                       es_predeterminada: bool = False) -> int:
    """Registra una presentación y devuelve su identificador."""
    return ejecutar("""
        INSERT INTO presentacion
            (id_producto, id_unidad, factor, precio_venta, es_predeterminada)
        VALUES (?, ?, ?, ?, ?)
    """, (id_producto, id_unidad, factor, precio_venta,
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

# =====================================================================
# Lotes
# =====================================================================


def listar_lotes(id_producto: int, solo_con_existencia: bool = True) -> list:
    """
    Devuelve los lotes de un producto con su existencia calculada.

    Se ordenan por fecha de caducidad para que al vender salga primero
    el que vence antes, que es la práctica que evita mermas.
    """
    filtro = 'HAVING existencia_lote > 0' if solo_con_existencia else ''
    return consultar(f"""
        SELECT
            l.id_lote,
            l.numero_lote,
            l.fecha_caducidad,
            l.fecha_entrada,
            COALESCE(SUM(m.cantidad), 0) AS existencia_lote
        FROM lote l
        LEFT JOIN movimiento m ON m.id_lote = l.id_lote
        WHERE l.id_producto = ?
        GROUP BY l.id_lote
        {filtro}
        ORDER BY l.fecha_caducidad IS NULL, l.fecha_caducidad
    """, (id_producto,))


def crear_lote(id_producto: int, numero_lote: str = None,
               fecha_caducidad: str = None, observaciones: str = None) -> int:
    """
    Registra un lote y devuelve su identificador.

    El número y la fecha admiten nulos porque no siempre vienen en el
    empaque. Es preferible que falten y se note, a capturar un dato
    inventado.
    """
    return ejecutar("""
        INSERT INTO lote (id_producto, numero_lote, fecha_caducidad, observaciones)
        VALUES (?, ?, ?, ?)
    """, (id_producto, numero_lote, fecha_caducidad, observaciones))


# =====================================================================
# Movimientos de inventario
# =====================================================================


def registrar_movimiento(id_producto: int, tipo: str, cantidad: float,
                         id_lote: int = None, costo_unitario: float = None,
                         referencia: str = None,
                         observaciones: str = None) -> int:
    """
    Registra un movimiento de inventario en unidad base.

    El signo lo define el tipo, no quien llama a la función. Las salidas
    y las mermas se guardan en negativo, de modo que la existencia sea
    siempre la suma de los movimientos.
    """
    TIPOS = ('entrada', 'salida', 'ajuste', 'merma')
    if tipo not in TIPOS:
        raise ValueError(f'Tipo de movimiento no válido: {tipo}')

    cantidad = abs(cantidad)
    if cantidad == 0:
        raise ValueError('La cantidad del movimiento no puede ser cero')

    if tipo in ('salida', 'merma'):
        cantidad = -cantidad

    return ejecutar("""
        INSERT INTO movimiento
            (id_producto, id_lote, tipo, cantidad, costo_unitario,
             referencia, observaciones)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (id_producto, id_lote, tipo, cantidad, costo_unitario,
          referencia, observaciones))


def registrar_ajuste(id_producto: int, existencia_contada: float,
                     observaciones: str = None):
    """
    Corrige la existencia tras un conteo físico.

    Calcula la diferencia contra lo que el sistema tiene registrado y
    genera el movimiento solo si hay discrepancia. Devuelve la
    diferencia aplicada, o cero si el conteo coincidía.
    """
    producto = obtener_producto(id_producto)
    if producto is None:
        raise ValueError(f'No existe el producto {id_producto}')

    diferencia = existencia_contada - producto['existencia']
    if diferencia == 0:
        return 0

    ejecutar("""
        INSERT INTO movimiento
            (id_producto, tipo, cantidad, referencia, observaciones)
        VALUES (?, 'ajuste', ?, 'Conteo físico', ?)
    """, (id_producto, diferencia, observaciones))
    return diferencia


def historial_movimientos(id_producto: int, limite: int = 50) -> list:
    """Devuelve los movimientos recientes de un producto."""
    return consultar("""
        SELECT
            m.id_movimiento,
            m.tipo,
            m.cantidad,
            m.fecha,
            m.referencia,
            m.observaciones,
            l.numero_lote
        FROM movimiento m
        LEFT JOIN lote l ON l.id_lote = m.id_lote
        WHERE m.id_producto = ?
        ORDER BY m.fecha DESC, m.id_movimiento DESC
        LIMIT ?
    """, (id_producto, limite))


# =====================================================================
# Ventas
# =====================================================================


def siguiente_folio(prefijo: str = 'N') -> str:
    """
    Genera el siguiente folio consecutivo de nota.

    Usa un prefijo propio del sistema para no chocar con los folios
    impresos del talonario, que seguirán existiendo mientras ambos
    convivan.
    """
    fila = consultar_una("""
        SELECT folio FROM venta
        WHERE folio LIKE ?
        ORDER BY LENGTH(folio) DESC, folio DESC
        LIMIT 1
    """, (f'{prefijo}-%',))

    if fila is None:
        return f'{prefijo}-00001'

    try:
        consecutivo = int(fila['folio'].split('-')[-1]) + 1
    except (ValueError, IndexError):
        consecutivo = 1
    return f'{prefijo}-{consecutivo:05d}'


def obtener_venta(id_venta: int):
    """Devuelve el encabezado de una venta, o None."""
    return consultar_una('SELECT * FROM venta WHERE id_venta = ?', (id_venta,))


def detalle_de_venta(id_venta: int) -> list:
    """Devuelve los renglones de una venta, listos para imprimir la nota."""
    return consultar("""
        SELECT
            d.id_detalle,
            p.clave_interna,
            p.descripcion,
            COALESCE(up.nombre, u.nombre) AS presentacion,
            d.cantidad,
            d.cantidad_base,
            d.precio_unitario,
            d.importe
        FROM venta_detalle d
        JOIN producto p ON p.id_producto = d.id_producto
        JOIN unidad   u ON u.id_unidad   = p.id_unidad
        LEFT JOIN presentacion pr ON pr.id_presentacion = d.id_presentacion
        LEFT JOIN unidad       up ON up.id_unidad       = pr.id_unidad
        WHERE d.id_venta = ?
        ORDER BY d.id_detalle
    """, (id_venta,))


def ventas_del_dia(fecha: str = None) -> list:
    """
    Devuelve las ventas de un día, con su número de renglones.

    Sin fecha, toma el día actual. Es la consulta del corte diario.
    """
    condicion = 'date(fecha) = ?' if fecha else "date(fecha) = date('now', 'localtime')"
    parametros = (fecha,) if fecha else ()
    return consultar(f"""
        SELECT
            v.id_venta,
            v.folio,
            v.fecha,
            v.cliente,
            v.forma_pago,
            v.total,
            COUNT(d.id_detalle) AS renglones
        FROM venta v
        LEFT JOIN venta_detalle d ON d.id_venta = v.id_venta
        WHERE {condicion}
        GROUP BY v.id_venta
        ORDER BY v.fecha DESC
    """, parametros)


def creditos_pendientes() -> list:
    """Ventas a crédito que siguen sin liquidarse."""
    return consultar("""
        SELECT id_venta, folio, date(fecha) AS fecha, cliente, total
        FROM venta
        WHERE forma_pago = 'credito' AND credito_pagado = 0
        ORDER BY fecha
    """)


def marcar_credito_pagado(id_venta: int) -> None:
    """Registra que un crédito quedó liquidado."""
    ejecutar('UPDATE venta SET credito_pagado = 1 WHERE id_venta = ?',
             (id_venta,))


# =====================================================================
# Mantenimiento de proveedores y categorías
# =====================================================================


def actualizar_proveedor(id_proveedor: int, nombre: str = None,
                         activo: bool = None, observaciones: str = None) -> None:
    """Modifica los datos de un proveedor."""
    cambios = {}
    if nombre is not None:
        cambios['nombre'] = nombre.strip()
    if activo is not None:
        cambios['activo'] = 1 if activo else 0
    if observaciones is not None:
        cambios['observaciones'] = observaciones
    if not cambios:
        return

    asignaciones = ', '.join(f'{campo} = ?' for campo in cambios)
    ejecutar(f'UPDATE proveedor SET {asignaciones} WHERE id_proveedor = ?',
             tuple(list(cambios.values()) + [id_proveedor]))


def productos_de_proveedor(id_proveedor: int) -> int:
    """Cuenta cuántos productos dependen de un proveedor."""
    fila = consultar_una(
        'SELECT COUNT(*) AS total FROM producto WHERE id_proveedor = ?',
        (id_proveedor,))
    return fila['total']


def eliminar_proveedor(id_proveedor: int) -> None:
    """
    Elimina un proveedor que no tenga productos asociados.

    Si ya tiene productos, no se borra: se desactiva. Borrarlo dejaría
    renglones apuntando a un proveedor inexistente.
    """
    if productos_de_proveedor(id_proveedor) > 0:
        raise ValueError(
            'El proveedor tiene productos asociados. Se puede desactivar, '
            'pero no eliminar.')
    ejecutar('DELETE FROM proveedor WHERE id_proveedor = ?', (id_proveedor,))


def actualizar_categoria(id_categoria: int, nombre: str = None,
                         maneja_caducidad: bool = None) -> None:
    """
    Modifica una categoría.

    El cambio de caducidad afecta solo a los productos que se den de
    alta a partir de ahora, porque cada producto conserva su propio
    indicador desde el momento en que se registró.
    """
    cambios = {}
    if nombre is not None:
        cambios['nombre'] = nombre.strip()
    if maneja_caducidad is not None:
        cambios['maneja_caducidad'] = 1 if maneja_caducidad else 0
    if not cambios:
        return

    asignaciones = ', '.join(f'{campo} = ?' for campo in cambios)
    ejecutar(f'UPDATE categoria SET {asignaciones} WHERE id_categoria = ?',
             tuple(list(cambios.values()) + [id_categoria]))


def productos_de_categoria(id_categoria: int) -> int:
    """Cuenta cuántos productos dependen de una categoría."""
    fila = consultar_una(
        'SELECT COUNT(*) AS total FROM producto WHERE id_categoria = ?',
        (id_categoria,))
    return fila['total']


def eliminar_categoria(id_categoria: int) -> None:
    """Elimina una categoría que no tenga productos asociados."""
    if productos_de_categoria(id_categoria) > 0:
        raise ValueError(
            'La categoría tiene productos asociados y no puede eliminarse.')
    ejecutar('DELETE FROM categoria WHERE id_categoria = ?', (id_categoria,))


def aplicar_caducidad_de_categoria(id_categoria: int) -> int:
    """
    Copia el indicador de caducidad de una categoría a sus productos.

    Sirve para corregir una clasificación equivocada sin tener que
    editar producto por producto. Devuelve cuántos productos cambiaron.
    """
    categoria = consultar_una(
        'SELECT maneja_caducidad FROM categoria WHERE id_categoria = ?',
        (id_categoria,))
    if categoria is None:
        return 0

    with conexion_abierta() as conexion:
        cursor = conexion.execute("""
            UPDATE producto
            SET maneja_caducidad = ?
            WHERE id_categoria = ? AND maneja_caducidad <> ?
        """, (categoria['maneja_caducidad'], id_categoria,
              categoria['maneja_caducidad']))
        return cursor.rowcount


def obtener_presentacion(id_presentacion: int):
    """Devuelve una presentación, o None."""
    return consultar_una(
        'SELECT * FROM presentacion WHERE id_presentacion = ?',
        (id_presentacion,))


def actualizar_presentacion(id_presentacion: int, nombre: int = None,
                            factor: float = None, precio_venta: float = None,
                            es_predeterminada: bool = None) -> None:
    """
    Modifica una presentación.

    Al marcar una como predeterminada, las demás del mismo producto
    dejan de serlo, porque solo puede ofrecerse una primero al vender.
    """
    cambios = {}
    if nombre is not None:
        cambios['id_unidad'] = nombre
    if factor is not None:
        cambios['factor'] = factor
    if precio_venta is not None:
        cambios['precio_venta'] = precio_venta
    if es_predeterminada is not None:
        cambios['es_predeterminada'] = 1 if es_predeterminada else 0

    if not cambios:
        return

    presentacion = obtener_presentacion(id_presentacion)
    if presentacion is None:
        return

    with conexion_abierta() as conexion:
        if cambios.get('es_predeterminada') == 1:
            conexion.execute("""
                UPDATE presentacion SET es_predeterminada = 0
                WHERE id_producto = ?
            """, (presentacion['id_producto'],))

        asignaciones = ', '.join(f'{campo} = ?' for campo in cambios)
        conexion.execute(
            f'UPDATE presentacion SET {asignaciones} WHERE id_presentacion = ?',
            tuple(list(cambios.values()) + [id_presentacion]))


def ventas_con_presentacion(id_presentacion: int) -> int:
    """Cuenta cuántas ventas usaron una presentación."""
    fila = consultar_una(
        'SELECT COUNT(*) AS total FROM venta_detalle WHERE id_presentacion = ?',
        (id_presentacion,))
    return fila['total']


def eliminar_presentacion(id_presentacion: int) -> None:
    """
    Elimina una presentación que no se haya usado en ninguna venta.

    Si ya se vendió con ella, borrarla dejaría renglones históricos sin
    forma de saber qué se cobró.
    """
    if ventas_con_presentacion(id_presentacion) > 0:
        raise ValueError(
            'La presentación ya se usó en ventas y no puede eliminarse.')
    ejecutar('DELETE FROM presentacion WHERE id_presentacion = ?',
             (id_presentacion,))


def productos_desalineados(id_categoria: int) -> int:
    """
    Cuenta los productos cuyo indicador de caducidad difiere del de su
    categoría.

    Sirve para ofrecer la corrección solo cuando hace falta, en lugar de
    mostrar siempre un botón que casi nunca se usa.
    """
    fila = consultar_una("""
        SELECT COUNT(*) AS total
        FROM producto p
        JOIN categoria c ON c.id_categoria = p.id_categoria
        WHERE p.id_categoria = ?
          AND p.maneja_caducidad <> c.maneja_caducidad
    """, (id_categoria,))
    return fila['total']


def obtener_lote(id_lote: int):
    """Devuelve un lote con su existencia calculada, o None."""
    return consultar_una("""
        SELECT
            l.id_lote,
            l.id_producto,
            l.numero_lote,
            l.fecha_caducidad,
            l.fecha_entrada,
            l.observaciones,
            COALESCE(SUM(m.cantidad), 0) AS existencia_lote
        FROM lote l
        LEFT JOIN movimiento m ON m.id_lote = l.id_lote
        WHERE l.id_lote = ?
        GROUP BY l.id_lote
    """, (id_lote,))


def actualizar_lote(id_lote: int, numero_lote: str = None,
                    fecha_caducidad: str = None,
                    observaciones: str = None) -> None:
    """
    Corrige los datos descriptivos de un lote.

    El número y la fecha no afectan la existencia ni el importe, por lo
    que pueden corregirse directamente. Las cantidades, en cambio, se
    corrigen con un ajuste que deja constancia.
    """
    cambios = {}
    if numero_lote is not None:
        cambios['numero_lote'] = numero_lote.strip() or None
    if fecha_caducidad is not None:
        cambios['fecha_caducidad'] = fecha_caducidad or None
    if observaciones is not None:
        cambios['observaciones'] = observaciones.strip() or None
    if not cambios:
        return

    asignaciones = ', '.join(f'{campo} = ?' for campo in cambios)
    ejecutar(f'UPDATE lote SET {asignaciones} WHERE id_lote = ?',
             tuple(list(cambios.values()) + [id_lote]))


def obtener_movimiento(id_movimiento: int):
    """Devuelve un movimiento con los datos de su producto, o None."""
    return consultar_una("""
        SELECT
            m.*,
            p.clave_interna,
            p.descripcion,
            u.nombre AS unidad,
            u.plural AS unidad_plural,
            l.numero_lote
        FROM movimiento m
        JOIN producto p ON p.id_producto = m.id_producto
        JOIN unidad   u ON u.id_unidad   = p.id_unidad
        LEFT JOIN lote l ON l.id_lote = m.id_lote
        WHERE m.id_movimiento = ?
    """, (id_movimiento,))


def movimientos_recientes(limite: int = 50, referencia: str = None) -> list:
    """
    Devuelve los movimientos más recientes de todo el inventario.

    Permite filtrar por referencia para recuperar los renglones de una
    factura y revisar lo que se capturó en ella.
    """
    condicion = 'WHERE m.referencia = ?' if referencia else ''
    parametros = (referencia, limite) if referencia else (limite,)
    return consultar(f"""
        SELECT
            m.id_movimiento,
            m.tipo,
            m.cantidad,
            m.costo_unitario,
            m.fecha,
            m.referencia,
            m.observaciones,
            m.id_lote,
            p.id_producto,
            p.clave_interna,
            p.descripcion,
            u.nombre AS unidad,
            u.plural AS unidad_plural,
            l.numero_lote,
            l.fecha_caducidad
        FROM movimiento m
        JOIN producto p ON p.id_producto = m.id_producto
        JOIN unidad   u ON u.id_unidad   = p.id_unidad
        LEFT JOIN lote l ON l.id_lote = m.id_lote
        {condicion}
        ORDER BY m.fecha DESC, m.id_movimiento DESC
        LIMIT ?
    """, parametros)


def referencias_recientes(limite: int = 30) -> list:
    """Devuelve las últimas referencias de entrada registradas."""
    return consultar("""
        SELECT
            referencia,
            COUNT(*)      AS renglones,
            MAX(fecha)    AS fecha
        FROM movimiento
        WHERE tipo = 'entrada' AND referencia IS NOT NULL
        GROUP BY referencia
        ORDER BY fecha DESC
        LIMIT ?
    """, (limite,))
