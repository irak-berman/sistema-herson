# -*- coding: utf-8 -*-
"""
Reglas de negocio del sistema de inventario.

Aquí vive la lógica que no pertenece ni a la base de datos ni a la
pantalla. La interfaz llama a estas funciones y recibe resultados ya
validados, de modo que las reglas se apliquen igual sin importar desde
qué pantalla se opere.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import math

import repositorio as repo
from conexion import conexion_abierta

# Porcentaje de la existencia inicial que define la mínima por producto.
# Criterio acordado con el propietario, descrito en el documento del
# modelo de datos.
PORCENTAJE_EXISTENCIA_MINIMA = 0.15


class ReglaDeNegocio(Exception):
    """Error que el usuario puede corregir, no una falla del sistema."""


# =====================================================================
# Cálculos de inventario
# =====================================================================


def calcular_existencia_minima(existencia_inicial: float) -> int:
    """
    Calcula la existencia mínima de un producto a partir de la que tiene
    al cargarse por primera vez.

    Se toma el 15 por ciento, redondeado hacia arriba y nunca menor a
    una pieza. Con este criterio un producto de 200 unidades queda en
    30, que coincide con la referencia del propietario, y un
    instrumental de 5 unidades queda en 1, que es lo razonable.
    """
    if existencia_inicial <= 0:
        return 1
    return max(1, math.ceil(existencia_inicial * PORCENTAJE_EXISTENCIA_MINIMA))


def convertir_a_unidad_base(cantidad: float, factor: float) -> float:
    """Convierte una cantidad de una presentación a la unidad base."""
    if factor <= 0:
        raise ReglaDeNegocio('El factor de conversión debe ser mayor que cero')
    return cantidad * factor


# =====================================================================
# Entrada de mercancía
# =====================================================================


def recibir_mercancia(id_producto: int, cantidad: float,
                      costo_unitario: float = None,
                      numero_lote: str = None, fecha_caducidad: str = None,
                      referencia: str = None) -> dict:
    """
    Registra la entrada de mercancía de un producto.

    Si el producto maneja caducidad, crea el lote y asocia la entrada a
    él. Si además se indica un costo distinto al registrado, actualiza
    el costo del catálogo, porque es el que se usa para valuar el
    inventario y calcular la utilidad.
    """
    producto = repo.obtener_producto(id_producto)
    if producto is None:
        raise ReglaDeNegocio('El producto no existe')
    if cantidad <= 0:
        raise ReglaDeNegocio('La cantidad recibida debe ser mayor que cero')

    id_lote = None
    if producto['maneja_caducidad'] if 'maneja_caducidad' in producto.keys() else False:
        id_lote = repo.crear_lote(id_producto, numero_lote, fecha_caducidad)
    elif numero_lote or fecha_caducidad:
        # Se registra el lote aunque el producto no lo exija, si el
        # usuario capturó el dato
        id_lote = repo.crear_lote(id_producto, numero_lote, fecha_caducidad)

    repo.registrar_movimiento(
        id_producto, 'entrada', cantidad,
        id_lote=id_lote, costo_unitario=costo_unitario, referencia=referencia
    )

    if costo_unitario is not None and costo_unitario != producto['costo_unitario']:
        repo.actualizar_producto(id_producto, costo_unitario=costo_unitario)

    return {
        'id_lote': id_lote,
        'existencia': repo.obtener_producto(id_producto)['existencia'],
    }


# =====================================================================
# Venta
# =====================================================================


def preparar_renglon(id_producto: int, cantidad: float,
                     id_presentacion: int = None) -> dict:
    """
    Arma un renglón de venta y calcula su equivalente en unidad base.

    Devuelve un diccionario con todo lo que la nota necesita, sin
    escribir nada en la base. La pantalla usa esto para ir formando el
    carrito antes de confirmar la venta.
    """
    producto = repo.obtener_producto(id_producto)
    if producto is None:
        raise ReglaDeNegocio('El producto no existe')
    if cantidad <= 0:
        raise ReglaDeNegocio('La cantidad debe ser mayor que cero')

    factor = 1.0
    precio = producto['precio_venta']
    nombre_presentacion = producto['unidad_base']

    if id_presentacion is not None:
        presentaciones = {p['id_presentacion']: p
                          for p in repo.listar_presentaciones(id_producto)}
        presentacion = presentaciones.get(id_presentacion)
        if presentacion is None:
            raise ReglaDeNegocio('La presentación no corresponde al producto')
        factor = presentacion['factor']
        precio = presentacion['precio_venta']
        nombre_presentacion = presentacion['nombre']

    cantidad_base = convertir_a_unidad_base(cantidad, factor)

    return {
        'id_producto': id_producto,
        'id_presentacion': id_presentacion,
        'clave_interna': producto['clave_interna'],
        'descripcion': producto['descripcion'],
        'presentacion': nombre_presentacion,
        'cantidad': cantidad,
        'cantidad_base': cantidad_base,
        'precio_unitario': precio,
        'importe': round(cantidad * precio, 2),
        'existencia_actual': producto['existencia'],
    }


def validar_existencia(renglones: list) -> list:
    """
    Revisa si algún renglón excede la existencia disponible.

    Devuelve la lista de avisos. No impide la venta, porque el sistema
    puede ir desfasado del anaquel mientras convive con el registro
    manual, pero sí advierte antes de confirmar.
    """
    requerido = {}
    for renglon in renglones:
        clave = renglon['id_producto']
        requerido[clave] = requerido.get(clave, 0) + renglon['cantidad_base']

    avisos = []
    for id_producto, cantidad in requerido.items():
        producto = repo.obtener_producto(id_producto)
        if cantidad > producto['existencia']:
            avisos.append(
                f'{producto["descripcion"]}: se piden {cantidad:g} '
                f'{producto["unidad_base"]} y hay {producto["existencia"]:g}'
            )
    return avisos


def _lote_a_descontar(id_producto: int, cantidad_base: float):
    """
    Elige el lote del que conviene descontar.

    Toma el que caduca primero y tiene existencia suficiente. Si ninguno
    alcanza, devuelve el primero disponible y deja que la existencia
    quede negativa en ese lote, que es una señal visible de que el
    registro de lotes no está al día.
    """
    lotes = repo.listar_lotes(id_producto, solo_con_existencia=True)
    if not lotes:
        return None
    for lote in lotes:
        if lote['existencia_lote'] >= cantidad_base:
            return lote['id_lote']
    return lotes[0]['id_lote']


def registrar_venta(renglones: list, forma_pago: str = 'efectivo',
                    cliente: str = None, descuento: float = 0,
                    requiere_factura: bool = False,
                    observaciones: str = None) -> dict:
    """
    Registra una venta completa en una sola transacción.

    Guarda el encabezado, sus renglones y los movimientos de salida de
    inventario. Si algo falla a la mitad, no queda nada escrito, de modo
    que nunca exista una nota sin productos ni un descuento de
    inventario sin venta que lo respalde.
    """
    if not renglones:
        raise ReglaDeNegocio('La venta no tiene renglones')

    FORMAS = ('efectivo', 'transferencia', 'credito')
    if forma_pago not in FORMAS:
        raise ReglaDeNegocio(f'Forma de pago no válida: {forma_pago}')

    subtotal = sum(renglon['importe'] for renglon in renglones)
    total = round(subtotal - descuento, 2)
    if total < 0:
        raise ReglaDeNegocio('El descuento no puede ser mayor que el total')

    if forma_pago == 'credito' and not (cliente or '').strip():
        raise ReglaDeNegocio('Una venta a crédito requiere el nombre del cliente')

    folio = repo.siguiente_folio()

    # El lote se elige antes de abrir la transacción, para no mezclar
    # consultas de apoyo con la escritura
    lotes = {
        indice: _lote_a_descontar(renglon['id_producto'], renglon['cantidad_base'])
        for indice, renglon in enumerate(renglones)
    }

    with conexion_abierta() as conexion:
        cursor = conexion.execute("""
            INSERT INTO venta
                (folio, cliente, forma_pago, credito_pagado,
                 requiere_factura, descuento, total, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (folio, (cliente or '').strip() or None, forma_pago,
              0 if forma_pago == 'credito' else 1,
              1 if requiere_factura else 0, descuento, total, observaciones))
        id_venta = cursor.lastrowid

        for indice, renglon in enumerate(renglones):
            conexion.execute("""
                INSERT INTO venta_detalle
                    (id_venta, id_producto, id_presentacion,
                     cantidad, cantidad_base, precio_unitario, importe)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (id_venta, renglon['id_producto'], renglon['id_presentacion'],
                  renglon['cantidad'], renglon['cantidad_base'],
                  renglon['precio_unitario'], renglon['importe']))

            conexion.execute("""
                INSERT INTO movimiento
                    (id_producto, id_lote, tipo, cantidad, referencia)
                VALUES (?, ?, 'salida', ?, ?)
            """, (renglon['id_producto'], lotes[indice],
                  -renglon['cantidad_base'], folio))

    return {'id_venta': id_venta, 'folio': folio,
            'subtotal': round(subtotal, 2), 'total': total}


def cancelar_venta(id_venta: int, motivo: str = None) -> None:
    """
    Cancela una venta y devuelve la mercancía al inventario.

    No borra la venta, porque el folio ya se entregó al cliente. Genera
    los movimientos inversos y deja constancia en las observaciones, de
    modo que el histórico conserve lo que realmente ocurrió.
    """
    venta = repo.obtener_venta(id_venta)
    if venta is None:
        raise ReglaDeNegocio('La venta no existe')
    if (venta['observaciones'] or '').startswith('CANCELADA'):
        raise ReglaDeNegocio('La venta ya estaba cancelada')

    renglones = repo.detalle_de_venta(id_venta)

    with conexion_abierta() as conexion:
        for renglon in renglones:
            conexion.execute("""
                INSERT INTO movimiento
                    (id_producto, tipo, cantidad, referencia, observaciones)
                VALUES (
                    (SELECT id_producto FROM producto WHERE clave_interna = ?),
                    'ajuste', ?, ?, 'Cancelación de venta'
                )
            """, (renglon['clave_interna'], renglon['cantidad_base'],
                  venta['folio']))

        nota = f'CANCELADA. {motivo}' if motivo else 'CANCELADA'
        conexion.execute(
            'UPDATE venta SET observaciones = ?, total = 0 WHERE id_venta = ?',
            (nota, id_venta))


# =====================================================================
# Carga inicial
# =====================================================================


def alta_rapida(descripcion: str, id_categoria: int, id_proveedor: int,
                existencia: float, costo_unitario: float,
                precio_venta: float, id_unidad: int,
                clave_proveedor: str = None) -> int:
    """
    Da de alta un producto con su existencia inicial en un solo paso.

    Calcula la existencia mínima con el criterio acordado y registra la
    existencia como un ajuste de entrada, de modo que quede trazada en
    el historial igual que cualquier otro movimiento.
    """
    minima = calcular_existencia_minima(existencia)

    id_producto = repo.crear_producto(
        descripcion=descripcion,
        id_categoria=id_categoria,
        id_proveedor=id_proveedor,
        clave_proveedor=clave_proveedor,
        id_unidad=id_unidad,
        costo_unitario=costo_unitario,
        precio_venta=precio_venta,
        existencia_minima=minima,
    )

    if existencia > 0:
        repo.registrar_movimiento(
            id_producto, 'entrada', existencia,
            costo_unitario=costo_unitario, referencia='Carga inicial'
        )

    return id_producto
