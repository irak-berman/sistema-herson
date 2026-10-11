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
import sesion
from conexion import conexion_abierta, consultar_una

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
        repo.actualizar_producto(
            id_producto, costo_unitario=costo_unitario,
            motivo=f'Costo de la recepción {referencia}' if referencia
                   else 'Costo actualizado al recibir mercancía')

    return {
        'id_lote': id_lote,
        'existencia': repo.obtener_producto(id_producto)['existencia'],
    }


# =====================================================================
# Venta
# =====================================================================


def preparar_renglon(id_producto: int, cantidad: float,
                     id_presentacion: int = None,
                     descuento: float = 0) -> dict:
    """
    Arma un renglón de venta y calcula su equivalente en unidad base.

    Devuelve un diccionario con todo lo que la nota necesita, sin
    escribir nada en la base. La pantalla usa esto para ir formando el
    carrito antes de confirmar la venta.

    El precio sale del catálogo y no se recibe como parámetro, porque
    quien atiende el mostrador no modifica precios. Lo que sí puede
    conceder es un descuento, que viaja aparte y queda a la vista en la
    nota.
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

    importe_bruto = round(cantidad * precio, 2)
    descuento = round(max(0.0, float(descuento or 0)), 2)
    if descuento > importe_bruto:
        raise ReglaDeNegocio(
            'El descuento no puede ser mayor que el importe del renglón')

    return {
        'id_producto': id_producto,
        'id_presentacion': id_presentacion,
        'clave_interna': producto['clave_interna'],
        'descripcion': producto['descripcion'],
        'presentacion': nombre_presentacion,
        'cantidad': cantidad,
        'cantidad_base': cantidad_base,
        'precio_unitario': precio,
        'importe_bruto': importe_bruto,
        'descuento': descuento,
        'importe': round(importe_bruto - descuento, 2),
        'existencia_actual': producto['existencia'],
    }


def repartir_descuento(renglones: list, descuento_total: float) -> list:
    """
    Reparte una rebaja sobre el total de la nota entre sus renglones.

    Cuando el propietario deja una nota en un número redondo, la rebaja
    no corresponde a un producto en particular. Como el descuento se
    guarda por renglón, hay que repartirlo, y se hace en proporción al
    importe de cada uno para que ningún producto cargue con una rebaja
    que no le toca.

    Los centavos que sobran del redondeo se cargan al renglón de mayor
    importe, de modo que la suma de los renglones dé exactamente la
    rebaja concedida y no un centavo de más o de menos.

    Devuelve una lista nueva. No modifica la que recibe.
    """
    descuento_total = round(max(0.0, float(descuento_total or 0)), 2)
    copias = [dict(renglon) for renglon in renglones]
    if descuento_total == 0 or not copias:
        return copias

    base = sum(renglon['importe'] for renglon in copias)
    if descuento_total > base:
        raise ReglaDeNegocio(
            'El descuento no puede ser mayor que el total de la nota')
    if base <= 0:
        return copias

    repartido = 0.0
    for renglon in copias:
        parte = round(descuento_total * renglon['importe'] / base, 2)
        renglon['descuento'] = round(renglon.get('descuento', 0) + parte, 2)
        renglon['importe'] = round(renglon['importe'] - parte, 2)
        repartido = round(repartido + parte, 2)

    sobrante = round(descuento_total - repartido, 2)
    if sobrante != 0:
        mayor = max(copias, key=lambda r: r['importe'])
        mayor['descuento'] = round(mayor['descuento'] + sobrante, 2)
        mayor['importe'] = round(mayor['importe'] - sobrante, 2)

    return copias


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

    El parámetro descuento es una rebaja sobre el total de la nota y se
    reparte entre los renglones antes de guardar. Los descuentos que ya
    traiga cada renglón se conservan y este se suma encima.
    """
    if not renglones:
        raise ReglaDeNegocio('La venta no tiene renglones')

    FORMAS = ('efectivo', 'transferencia', 'credito')
    if forma_pago not in FORMAS:
        raise ReglaDeNegocio(f'Forma de pago no válida: {forma_pago}')

    if forma_pago == 'credito' and not (cliente or '').strip():
        raise ReglaDeNegocio('Una venta a crédito requiere el nombre del cliente')

    # La rebaja global se convierte en rebaja por renglón, porque es ahí
    # donde vive el descuento desde que el margen se analiza por
    # producto.
    renglones = repartir_descuento(renglones, descuento)

    bruto = round(sum(renglon.get('importe_bruto',
                                  renglon['importe'] + renglon.get('descuento', 0))
                      for renglon in renglones), 2)
    descuento = round(sum(renglon.get('descuento', 0)
                          for renglon in renglones), 2)
    subtotal = bruto
    total = round(bruto - descuento, 2)
    if total < 0:
        raise ReglaDeNegocio('El descuento no puede ser mayor que el total')

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
                 requiere_factura, descuento, total, observaciones, usuario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (folio, (cliente or '').strip() or None, forma_pago,
              0 if forma_pago == 'credito' else 1,
              1 if requiere_factura else 0, descuento, total, observaciones,
              sesion.usuario_actual()))
        id_venta = cursor.lastrowid

        quien = sesion.usuario_actual()

        for indice, renglon in enumerate(renglones):
            conexion.execute("""
                INSERT INTO venta_detalle
                    (id_venta, id_producto, id_presentacion,
                     cantidad, cantidad_base, precio_unitario, importe,
                     descuento)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (id_venta, renglon['id_producto'], renglon['id_presentacion'],
                  renglon['cantidad'], renglon['cantidad_base'],
                  renglon['precio_unitario'], renglon['importe'],
                  renglon.get('descuento', 0) or 0))

            conexion.execute("""
                INSERT INTO movimiento
                    (id_producto, id_lote, tipo, cantidad, referencia,
                     usuario)
                VALUES (?, ?, 'salida', ?, ?, ?)
            """, (renglon['id_producto'], lotes[indice],
                  -renglon['cantidad_base'], folio, quien))

    return {'id_venta': id_venta, 'folio': folio,
            'subtotal': round(subtotal, 2), 'total': total}


def cancelar_venta(id_venta: int, motivo: str = None) -> None:
    """
    Cancela una venta y devuelve la mercancía al inventario.

    No borra la venta, porque el folio ya se entregó al cliente. Genera
    los movimientos inversos y marca el encabezado, de modo que el
    histórico conserve lo que realmente ocurrió.

    La marca es una columna y no una palabra dentro de las
    observaciones. Con la columna, la vista que alimenta el tablero
    puede dejar fuera las notas canceladas, que de otro modo seguirían
    contando como ingreso y como utilidad.

    El total del encabezado no se toca. Lo mantiene cuadrado con el
    detalle un disparador de la base, y lo que saca la venta del
    análisis es la marca, no un total puesto en cero.
    """
    venta = repo.obtener_venta(id_venta)
    if venta is None:
        raise ReglaDeNegocio('La venta no existe')
    if venta['cancelada']:
        raise ReglaDeNegocio('La venta ya estaba cancelada')

    renglones = repo.detalle_de_venta(id_venta)
    quien = sesion.usuario_actual()

    with conexion_abierta() as conexion:
        for renglon in renglones:
            conexion.execute("""
                INSERT INTO movimiento
                    (id_producto, tipo, cantidad, referencia,
                     observaciones, usuario)
                VALUES (
                    (SELECT id_producto FROM producto WHERE clave_interna = ?),
                    'ajuste', ?, ?, 'Cancelación de venta', ?
                )
            """, (renglon['clave_interna'], renglon['cantidad_base'],
                  venta['folio'], quien))

        conexion.execute("""
            UPDATE venta
               SET cancelada = 1,
                   fecha_cancelacion = datetime('now', 'localtime'),
                   usuario_cancelacion = ?,
                   motivo_cancelacion = ?
             WHERE id_venta = ?
        """, (quien, motivo, id_venta))


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


# =====================================================================
# Recepción de mercancía por factura
# =====================================================================


def calcular_costo_unitario(importe: float, piezas_cobradas: float,
                            piezas_bonificadas: float = 0,
                            incluye_iva: bool = True,
                            tasa_iva: float = 0.16) -> float:
    """
    Calcula el costo real de cada pieza recibida.

    Reproduce la operación que el propietario hace hoy con calculadora.
    El importe se reparte entre todas las piezas que entraron al
    almacén, incluidas las bonificadas, porque esas también se venden y
    abaratan el costo del lote completo.

    Ejemplo documentado en el diagnóstico: 27,525.03 pesos entre 240
    piezas, de las cuales 40 fueron bonificadas, da 114.69 pesos por
    pieza. El valor se guarda con toda su precisión y se redondea solo
    al mostrarlo, de modo que el inventario valuado cuadre contra las
    facturas y el usuario no vea cifras ilegibles.
    """
    recibidas = piezas_cobradas + piezas_bonificadas
    if recibidas <= 0:
        raise ReglaDeNegocio('Debe recibirse al menos una pieza')
    if importe < 0:
        raise ReglaDeNegocio('El importe no puede ser negativo')

    total = importe if incluye_iva else importe * (1 + tasa_iva)
    return total / recibidas


def preparar_recepcion(id_producto: int, piezas_cobradas: float,
                       piezas_bonificadas: float = 0, importe: float = None,
                       costo_unitario: float = None, incluye_iva: bool = True,
                       numero_lote: str = None,
                       fecha_caducidad: str = None) -> dict:
    """
    Arma un renglón de recepción sin escribir nada en la base.

    El costo puede capturarse ya calculado o derivarse del importe de la
    factura. Si se dan los dos, manda el importe, porque es el dato que
    viene del documento del proveedor.
    """
    producto = repo.obtener_producto(id_producto)
    if producto is None:
        raise ReglaDeNegocio('El producto no existe')

    # El indicador de caducidad vive en la tabla y no en la vista de
    # existencia, que está pensada para la consulta diaria.
    fila = consultar_una(
        'SELECT maneja_caducidad FROM producto WHERE id_producto = ?',
        (id_producto,))
    maneja_caducidad = bool(fila['maneja_caducidad'])

    recibidas = piezas_cobradas + piezas_bonificadas
    if recibidas <= 0:
        raise ReglaDeNegocio('Debe recibirse al menos una pieza')

    if importe is not None:
        costo = calcular_costo_unitario(
            importe, piezas_cobradas, piezas_bonificadas, incluye_iva)
    elif costo_unitario is not None:
        costo = costo_unitario
    else:
        costo = producto['costo_unitario']

    return {
        'id_producto': id_producto,
        'clave_interna': producto['clave_interna'],
        'descripcion': producto['descripcion'],
        'unidad': producto['unidad_base'],
        'unidad_plural': producto['unidad_plural'],
        'maneja_caducidad': maneja_caducidad,
        'piezas_cobradas': piezas_cobradas,
        'piezas_bonificadas': piezas_bonificadas,
        'recibidas': recibidas,
        'importe': importe,
        'costo_unitario': costo,
        'costo_anterior': producto['costo_unitario'],
        'numero_lote': numero_lote,
        'fecha_caducidad': fecha_caducidad,
    }


def recibir_factura(renglones: list, referencia: str = None,
                    observaciones: str = None) -> dict:
    """
    Registra la recepción completa de una factura en una sola operación.

    Por cada renglón crea el lote cuando corresponde, registra la
    entrada por el total de piezas recibidas y actualiza el costo del
    producto. Si algo falla a la mitad, no queda nada escrito, de modo
    que no exista una entrada de inventario sin su respaldo documental.
    """
    if not renglones:
        raise ReglaDeNegocio('La recepción no tiene renglones')

    with conexion_abierta() as conexion:
        for renglon in renglones:
            id_lote = None
            if renglon['maneja_caducidad'] or renglon['numero_lote'] \
                    or renglon['fecha_caducidad']:
                cursor = conexion.execute("""
                    INSERT INTO lote
                        (id_producto, numero_lote, fecha_caducidad)
                    VALUES (?, ?, ?)
                """, (renglon['id_producto'], renglon['numero_lote'],
                      renglon['fecha_caducidad']))
                id_lote = cursor.lastrowid

            conexion.execute("""
                INSERT INTO movimiento
                    (id_producto, id_lote, tipo, cantidad, costo_unitario,
                     referencia, observaciones)
                VALUES (?, ?, 'entrada', ?, ?, ?, ?)
            """, (renglon['id_producto'], id_lote, renglon['recibidas'],
                  renglon['costo_unitario'], referencia, observaciones))

            conexion.execute(
                'UPDATE producto SET costo_unitario = ? WHERE id_producto = ?',
                (renglon['costo_unitario'], renglon['id_producto']))

    total = sum(r['importe'] or 0 for r in renglones)
    return {
        'renglones': len(renglones),
        'piezas': sum(r['recibidas'] for r in renglones),
        'importe': round(total, 2),
    }


# =====================================================================
# Corrección de movimientos
# =====================================================================


def corregir_cantidad(id_movimiento: int, cantidad_correcta: float,
                      motivo: str = None) -> dict:
    """
    Corrige la cantidad de un movimiento ya registrado.

    No modifica el movimiento original, porque alterarlo dejaría un
    inventario que no puede explicar su propia historia. En su lugar
    genera un ajuste por la diferencia, que queda visible en el
    historial con el motivo de la corrección.
    """
    movimiento = repo.obtener_movimiento(id_movimiento)
    if movimiento is None:
        raise ReglaDeNegocio('El movimiento no existe')

    registrada = abs(movimiento['cantidad'])
    if cantidad_correcta < 0:
        raise ReglaDeNegocio('La cantidad no puede ser negativa')

    diferencia = cantidad_correcta - registrada
    if diferencia == 0:
        return {'diferencia': 0, 'id_ajuste': None}

    # El ajuste conserva el signo del movimiento corregido. Si una
    # entrada de 240 debía ser de 200, el ajuste resta 40. Si una salida
    # de 100 debía ser de 80, el ajuste suma 20.
    signo = 1 if movimiento['cantidad'] > 0 else -1
    ajuste = signo * diferencia

    nota = f'Corrección del movimiento {id_movimiento}'
    if motivo:
        nota += f'. {motivo}'

    # Se inserta directamente porque registrar_movimiento normaliza el
    # signo según el tipo, y aquí el signo ya viene calculado.
    with conexion_abierta() as conexion:
        cursor = conexion.execute("""
            INSERT INTO movimiento
                (id_producto, id_lote, tipo, cantidad, referencia,
                 observaciones)
            VALUES (?, ?, 'ajuste', ?, ?, ?)
        """, (movimiento['id_producto'], movimiento['id_lote'], ajuste,
              movimiento['referencia'], nota))
        id_ajuste = cursor.lastrowid

    return {'diferencia': ajuste, 'id_ajuste': id_ajuste}


def corregir_costo(id_movimiento: int, costo_correcto: float,
                   actualizar_producto: bool = True) -> None:
    """
    Corrige el costo registrado en una entrada.

    El costo es un dato informativo del movimiento y no afecta la
    existencia, por lo que puede corregirse directamente. Si se indica,
    también actualiza el costo vigente del producto.
    """
    movimiento = repo.obtener_movimiento(id_movimiento)
    if movimiento is None:
        raise ReglaDeNegocio('El movimiento no existe')
    if costo_correcto < 0:
        raise ReglaDeNegocio('El costo no puede ser negativo')

    with conexion_abierta() as conexion:
        conexion.execute(
            'UPDATE movimiento SET costo_unitario = ? WHERE id_movimiento = ?',
            (costo_correcto, id_movimiento))

        if actualizar_producto:
            # El costo anterior se lee antes de pisarlo, porque es lo
            # que va al historial.
            fila = conexion.execute(
                'SELECT costo_unitario FROM producto WHERE id_producto = ?',
                (movimiento['id_producto'],)).fetchone()
            costo_anterior = fila['costo_unitario'] if fila else None

            conexion.execute(
                'UPDATE producto SET costo_unitario = ? WHERE id_producto = ?',
                (costo_correcto, movimiento['id_producto']))

            # Esta función escribe con SQL directo y no pasa por
            # repo.actualizar_producto, así que el registro del cambio
            # se hace aquí. De otro modo, corregir el costo sería la
            # única manera de mover dinero sin dejar rastro.
            distinto = (costo_anterior is None
                        or abs(float(costo_anterior) - costo_correcto) >= 1e-9)
            if distinto:
                conexion.execute("""
                    INSERT INTO precio_historial
                        (id_producto, campo, valor_anterior, valor_nuevo,
                         usuario, motivo)
                    VALUES (?, 'costo_unitario', ?, ?, ?, ?)
                """, (movimiento['id_producto'], costo_anterior,
                      costo_correcto, sesion.usuario_actual(),
                      f'Corrección del costo en el movimiento '
                      f'{id_movimiento}'))
