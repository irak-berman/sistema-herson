# Modelo de datos

Sistema de control de inventario y análisis de ventas
Depósito Dental HERSON

Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
Actividad 2 del cronograma: diseño del modelo de datos

El diagrama se mantiene como código para que pueda regenerarse si el
modelo cambia durante el desarrollo. La fuente de verdad del esquema es
el archivo `basedatos/esquema.sql`.

## Diagrama entidad-relación

```mermaid
erDiagram
    PROVEEDOR ||--o{ PRODUCTO : surte
    CATEGORIA ||--o{ PRODUCTO : clasifica
    PRODUCTO ||--o{ PRESENTACION : presenta
    PRODUCTO ||--o{ LOTE : recibe
    PRODUCTO ||--o{ MOVIMIENTO : registra
    LOTE ||--o{ MOVIMIENTO : afecta
    VENTA ||--|{ VENTA_DETALLE : contiene
    PRODUCTO ||--o{ VENTA_DETALLE : vende
    PRESENTACION ||--o{ VENTA_DETALLE : determina

    PROVEEDOR {
        int id_proveedor PK
        text nombre UK
        int activo
        text observaciones
    }

    CATEGORIA {
        int id_categoria PK
        text nombre UK
        int maneja_caducidad
    }

    PRODUCTO {
        int id_producto PK
        text clave_interna UK
        text clave_proveedor
        text descripcion
        int id_categoria FK
        int id_proveedor FK
        text unidad_base
        real costo_unitario
        real precio_venta
        int existencia_minima
        int maneja_caducidad
        int activo
        text fecha_alta
    }

    PRESENTACION {
        int id_presentacion PK
        int id_producto FK
        text nombre
        real factor
        real precio_venta
        int es_predeterminada
    }

    LOTE {
        int id_lote PK
        int id_producto FK
        text numero_lote
        text fecha_caducidad
        text fecha_entrada
        text observaciones
    }

    MOVIMIENTO {
        int id_movimiento PK
        int id_producto FK
        int id_lote FK
        text tipo
        real cantidad
        real costo_unitario
        text fecha
        text referencia
        text observaciones
    }

    VENTA {
        int id_venta PK
        text folio UK
        text fecha
        text cliente
        text forma_pago
        int credito_pagado
        int requiere_factura
        real descuento
        real total
        text observaciones
    }

    VENTA_DETALLE {
        int id_detalle PK
        int id_venta FK
        int id_producto FK
        int id_presentacion FK
        real cantidad
        real cantidad_base
        real precio_unitario
        real importe
    }
```

## Notación

`||--o{` es una relación de uno a muchos donde el lado de muchos es
opcional. Un proveedor puede surtir varios productos o ninguno.

`||--|{` es una relación de uno a muchos obligatoria. Una venta tiene al
menos un renglón, porque una nota sin productos no existe.

`PK` es llave primaria, `FK` llave foránea y `UK` restricción de unicidad.

## Decisiones de diseño

**La existencia no se almacena, se calcula.** No hay columna de
existencia en `producto`. El dato se obtiene sumando los movimientos del
producto, lo que permite explicar en todo momento por qué hay lo que hay.
Guardar la existencia como campo fijo y además registrar movimientos
duplicaría el dato y reproduciría el problema que ya tiene el archivo de
Excel.

**La clave interna sustituye a la del proveedor.** En el inventario
actual hay 248 renglones sin clave y 75 claves repetidas en 316 filas,
porque cada proveedor usa su propia nomenclatura. La clave del proveedor
se conserva en una columna aparte, ya que sigue siendo necesaria para
hacer pedidos.

**Las presentaciones resuelven el mayoreo y el menudeo.** El factor de
conversión indica cuántas unidades base entrega cada presentación, de
modo que la venta de una caja descuente las piezas que contiene. Sin él,
la existencia se descuadra en la primera venta de mayoreo.

**El lote admite nulos.** El número de lote y la fecha de caducidad
vienen en el empaque y en la factura, pero no siempre. Es preferible que
el campo quede vacío y sea visible que falta, a obligar a capturar un
dato inventado.

**El precio se congela en el detalle de la venta.** El importe cobrado se
guarda tal como ocurrió, en lugar de leerse del catálogo, porque los
precios cambian y el histórico debe reflejar la realidad de cada venta.

**El cliente no tiene tabla propia.** Las notas del depósito registran el
nombre solo cuando hay crédito o factura, por lo que se almacena como
texto en la venta. Un catálogo de clientes sería construir algo que el
negocio no utiliza.

## Vistas

`v_existencia` entrega la existencia actual por producto a partir de la
suma de movimientos, junto con su categoría, proveedor, costo y precio.

`v_por_reabastecer` filtra los productos activos cuya existencia llegó o
bajó de la mínima configurada, y sustituye la revisión visual de
anaqueles del proceso actual.

`v_caducidad_proxima` lista los lotes con existencia que caducan dentro
de los siguientes 180 días, plazo definido por el propietario.

`v_ventas_plano` entrega una fila por renglón vendido, ya desnormalizada
y con la utilidad estimada calculada, que es la fuente del archivo que
consume el tablero de Power BI.
