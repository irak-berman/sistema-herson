-- =====================================================================
-- Sistema de control de inventario y análisis de ventas
-- Depósito Dental HERSON
--
-- Script de creación de la base de datos
-- Motor: SQLite 3
-- Autor: Irak Berman Gutiérrez
-- Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
-- Actividad 2 del cronograma: diseño del modelo de datos
-- =====================================================================

-- Las llaves foráneas están desactivadas por omisión en SQLite.
-- Sin esta línea, las relaciones se declaran pero no se validan.
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Tabla: proveedor
-- Hoy cada proveedor es una hoja distinta del libro de Excel. Al
-- convertirlos en renglones de una tabla, un mismo producto puede
-- consultarse sin abrir nueve hojas.
-- ---------------------------------------------------------------------
CREATE TABLE proveedor (
    id_proveedor     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT    NOT NULL UNIQUE,
    activo           INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    observaciones    TEXT
);

-- ---------------------------------------------------------------------
-- Tabla: categoria
-- Agrupa los productos y define el valor inicial del indicador de
-- caducidad durante la carga inicial. Los perecederos se marcan en 1 y
-- el instrumental, el equipo y el mobiliario en 0.
-- ---------------------------------------------------------------------
CREATE TABLE categoria (
    id_categoria     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT    NOT NULL UNIQUE,
    maneja_caducidad INTEGER NOT NULL DEFAULT 0
                     CHECK (maneja_caducidad IN (0, 1))
);

-- ---------------------------------------------------------------------
-- Tabla: unidad
-- Catálogo de unidades de medida. Existe para que el mismo concepto no
-- se guarde escrito de formas distintas, que es uno de los problemas
-- detectados en el archivo de Excel del depósito. Guarda también el
-- plural, de modo que los mensajes digan "30 piezas" y no "30 pieza".
-- ---------------------------------------------------------------------
CREATE TABLE unidad (
    id_unidad   INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT    NOT NULL UNIQUE,
    plural      TEXT    NOT NULL,
    activo      INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

-- Unidades iniciales. El propietario puede agregar o retirar las que
-- necesite desde la pantalla de catálogo.
INSERT INTO unidad (nombre, plural) VALUES
    ('pieza', 'piezas'),
    ('caja', 'cajas'),
    ('paquete', 'paquetes'),
    ('frasco', 'frascos'),
    ('bote', 'botes'),
    ('tubo', 'tubos'),
    ('sobre', 'sobres'),
    ('jeringa', 'jeringas'),
    ('rollo', 'rollos'),
    ('par', 'pares'),
    ('juego', 'juegos'),
    ('kit', 'kits');

-- ---------------------------------------------------------------------
-- Tabla: producto
-- Núcleo del catálogo. La clave interna resuelve el problema detectado
-- en el diagnóstico: 248 renglones sin clave y 75 claves repetidas en
-- 316 filas, porque los códigos actuales son del proveedor y no son
-- únicos entre proveedores.
-- La clave del proveedor se conserva aparte para poder hacer pedidos.
-- ---------------------------------------------------------------------
CREATE TABLE producto (
    id_producto       INTEGER PRIMARY KEY AUTOINCREMENT,
    clave_interna     TEXT    NOT NULL UNIQUE,
    clave_proveedor   TEXT,
    descripcion       TEXT    NOT NULL,
    id_categoria      INTEGER NOT NULL,
    id_proveedor      INTEGER,

    -- Unidad base en la que se controla la existencia. Todas las
    -- presentaciones se convierten a esta unidad.
    id_unidad         INTEGER NOT NULL,

    costo_unitario    REAL    NOT NULL DEFAULT 0 CHECK (costo_unitario >= 0),
    precio_venta      REAL    NOT NULL DEFAULT 0 CHECK (precio_venta >= 0),

    -- Existencia mínima por producto. El valor inicial se calcula como
    -- el 15 % de la existencia de la carga inicial, redondeado hacia
    -- arriba y nunca menor a 1, criterio acordado con el propietario.
    existencia_minima INTEGER NOT NULL DEFAULT 1
                      CHECK (existencia_minima >= 0),

    -- Se hereda de la categoría y puede ajustarse producto por producto.
    maneja_caducidad  INTEGER NOT NULL DEFAULT 0
                      CHECK (maneja_caducidad IN (0, 1)),

    -- 1 activo, 0 agotado o descontinuado. El propietario decide cuáles
    -- dar de baja; el sistema no los elimina por su cuenta.
    activo            INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),

    fecha_alta        TEXT    NOT NULL DEFAULT (date('now', 'localtime')),

    FOREIGN KEY (id_categoria) REFERENCES categoria (id_categoria),
    FOREIGN KEY (id_proveedor) REFERENCES proveedor (id_proveedor),
    FOREIGN KEY (id_unidad)    REFERENCES unidad (id_unidad)
);

-- Índices sobre las columnas que más se van a consultar al vender
CREATE INDEX idx_producto_descripcion ON producto (descripcion);
CREATE INDEX idx_producto_proveedor   ON producto (id_proveedor);

-- ---------------------------------------------------------------------
-- Tabla: presentacion
-- Resuelve que el depósito venda al por mayor y al menudeo. El mismo
-- producto sale por caja, por paquete o por pieza, y cada presentación
-- equivale a una cantidad distinta de la unidad base.
-- Ejemplo: una caja de guantes con factor 100 descuenta 100 piezas.
-- Sin esta tabla, la existencia se descuadra en la primera venta de
-- mayoreo.
-- ---------------------------------------------------------------------
CREATE TABLE presentacion (
    id_presentacion   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_producto       INTEGER NOT NULL,
    id_unidad         INTEGER NOT NULL,

    -- Cuántas unidades base entrega esta presentación
    factor            REAL    NOT NULL CHECK (factor > 0),

    precio_venta      REAL    NOT NULL CHECK (precio_venta >= 0),

    -- Marca la presentación que se ofrece por omisión al vender
    es_predeterminada INTEGER NOT NULL DEFAULT 0
                      CHECK (es_predeterminada IN (0, 1)),

    FOREIGN KEY (id_producto) REFERENCES producto (id_producto)
        ON DELETE CASCADE,
    FOREIGN KEY (id_unidad)   REFERENCES unidad (id_unidad),

    -- Un producto no puede tener dos presentaciones en la misma unidad
    UNIQUE (id_producto, id_unidad)
);

-- ---------------------------------------------------------------------
-- Tabla: lote
-- Solo aplica a los productos marcados con maneja_caducidad = 1.
-- El número de lote y la fecha se capturan al recibir la mercancía,
-- que es cuando el dato está disponible en el empaque y en la factura.
-- ---------------------------------------------------------------------
CREATE TABLE lote (
    id_lote          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_producto      INTEGER NOT NULL,

    -- Puede faltar en el empaque; por eso admite nulo
    numero_lote      TEXT,
    fecha_caducidad  TEXT,

    fecha_entrada    TEXT    NOT NULL DEFAULT (date('now', 'localtime')),
    observaciones    TEXT,

    FOREIGN KEY (id_producto) REFERENCES producto (id_producto)
);

CREATE INDEX idx_lote_caducidad ON lote (fecha_caducidad);
CREATE INDEX idx_lote_producto  ON lote (id_producto);

-- ---------------------------------------------------------------------
-- Tabla: movimiento
-- Registra toda variación de existencia. La existencia nunca se guarda
-- como dato fijo: se obtiene sumando los movimientos de un producto.
-- Así el sistema siempre puede explicar por qué hay lo que hay, que es
-- justo lo que el archivo de Excel no permite hoy.
-- ---------------------------------------------------------------------
CREATE TABLE movimiento (
    id_movimiento   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_producto     INTEGER NOT NULL,

    -- Solo se llena en productos que manejan caducidad
    id_lote         INTEGER,

    -- entrada: compra a proveedor
    -- salida:  venta al cliente
    -- ajuste:  corrección por conteo físico
    -- merma:   producto caducado o dañado
    tipo            TEXT    NOT NULL
                    CHECK (tipo IN ('entrada', 'salida', 'ajuste', 'merma')),

    -- Siempre en unidad base. Positiva en entradas y ajustes al alza,
    -- negativa en salidas, mermas y ajustes a la baja.
    cantidad        REAL    NOT NULL CHECK (cantidad <> 0),

    costo_unitario  REAL,
    fecha           TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    referencia      TEXT,
    observaciones   TEXT,

    FOREIGN KEY (id_producto) REFERENCES producto (id_producto),
    FOREIGN KEY (id_lote)     REFERENCES lote (id_lote)
);

CREATE INDEX idx_movimiento_producto ON movimiento (id_producto);
CREATE INDEX idx_movimiento_fecha    ON movimiento (fecha);

-- ---------------------------------------------------------------------
-- Tabla: venta
-- Encabezado de la nota. El cliente se guarda como texto y no como
-- tabla propia, porque las notas del depósito solo registran nombre
-- cuando hay crédito o factura. Crear un catálogo de clientes sería
-- construir algo que el negocio no utiliza.
-- ---------------------------------------------------------------------
CREATE TABLE venta (
    id_venta         INTEGER PRIMARY KEY AUTOINCREMENT,
    folio            TEXT    NOT NULL UNIQUE,
    fecha            TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    cliente          TEXT,

    forma_pago       TEXT    NOT NULL DEFAULT 'efectivo'
                     CHECK (forma_pago IN ('efectivo', 'transferencia', 'credito')),

    -- El crédito lo autoriza el propietario
    credito_pagado   INTEGER NOT NULL DEFAULT 1
                     CHECK (credito_pagado IN (0, 1)),

    requiere_factura INTEGER NOT NULL DEFAULT 0
                     CHECK (requiere_factura IN (0, 1)),

    descuento        REAL    NOT NULL DEFAULT 0 CHECK (descuento >= 0),
    total            REAL    NOT NULL DEFAULT 0 CHECK (total >= 0),
    observaciones    TEXT
);

CREATE INDEX idx_venta_fecha ON venta (fecha);

-- ---------------------------------------------------------------------
-- Tabla: venta_detalle
-- Los renglones de la nota. Se guarda el precio del momento de la venta
-- y no se lee del catálogo, porque los precios cambian y el histórico
-- debe reflejar lo que realmente se cobró.
-- ---------------------------------------------------------------------
CREATE TABLE venta_detalle (
    id_detalle      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venta        INTEGER NOT NULL,
    id_producto     INTEGER NOT NULL,
    id_presentacion INTEGER,

    cantidad        REAL    NOT NULL CHECK (cantidad > 0),

    -- Cantidad convertida a unidad base, que es la que descuenta
    cantidad_base   REAL    NOT NULL CHECK (cantidad_base > 0),

    precio_unitario REAL    NOT NULL CHECK (precio_unitario >= 0),
    importe         REAL    NOT NULL CHECK (importe >= 0),

    FOREIGN KEY (id_venta)        REFERENCES venta (id_venta) ON DELETE CASCADE,
    FOREIGN KEY (id_producto)     REFERENCES producto (id_producto),
    FOREIGN KEY (id_presentacion) REFERENCES presentacion (id_presentacion)
);

CREATE INDEX idx_detalle_venta    ON venta_detalle (id_venta);
CREATE INDEX idx_detalle_producto ON venta_detalle (id_producto);

-- =====================================================================
-- VISTAS
-- Consultas guardadas que resuelven lo que el sistema necesita mostrar.
-- Al vivir en la base de datos, la aplicación y el tablero de Power BI
-- leen exactamente la misma definición y no pueden dar cifras distintas.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Vista: v_existencia
-- Existencia actual por producto, obtenida de la suma de movimientos.
-- ---------------------------------------------------------------------
CREATE VIEW v_existencia AS
SELECT
    p.id_producto,
    p.clave_interna,
    p.descripcion,
    c.nombre                     AS categoria,
    pr.nombre                    AS proveedor,
    u.nombre                     AS unidad_base,
    u.plural                     AS unidad_plural,
    p.id_unidad,
    COALESCE(SUM(m.cantidad), 0) AS existencia,
    p.existencia_minima,
    p.costo_unitario,
    p.precio_venta,
    p.activo
FROM producto p
JOIN unidad u ON u.id_unidad = p.id_unidad
LEFT JOIN categoria  c  ON c.id_categoria  = p.id_categoria
LEFT JOIN proveedor  pr ON pr.id_proveedor = p.id_proveedor
LEFT JOIN movimiento m  ON m.id_producto   = p.id_producto
GROUP BY p.id_producto;

-- ---------------------------------------------------------------------
-- Vista: v_por_reabastecer
-- Productos cuya existencia llegó o bajó de la mínima configurada.
-- Sustituye la revisión visual de anaqueles del proceso actual.
-- ---------------------------------------------------------------------
CREATE VIEW v_por_reabastecer AS
SELECT *
FROM v_existencia
WHERE activo = 1
  AND existencia <= existencia_minima;

-- ---------------------------------------------------------------------
-- Vista: v_caducidad_proxima
-- Lotes con existencia que caducan dentro de los próximos 180 días,
-- plazo definido por el propietario. Los lotes sin fecha capturada
-- quedan fuera y se revisan aparte.
-- ---------------------------------------------------------------------
CREATE VIEW v_caducidad_proxima AS
SELECT
    l.id_lote,
    p.clave_interna,
    p.descripcion,
    l.numero_lote,
    l.fecha_caducidad,
    CAST(julianday(l.fecha_caducidad)
         - julianday(date('now', 'localtime')) AS INTEGER) AS dias_restantes,
    COALESCE(SUM(m.cantidad), 0)                           AS existencia_lote
FROM lote l
JOIN producto p ON p.id_producto = l.id_producto
LEFT JOIN movimiento m ON m.id_lote = l.id_lote
WHERE l.fecha_caducidad IS NOT NULL
GROUP BY l.id_lote
HAVING existencia_lote > 0
   AND dias_restantes <= 180
ORDER BY dias_restantes;

-- ---------------------------------------------------------------------
-- Vista: v_ventas_plano
-- Una fila por renglón vendido, ya desnormalizada. Es la fuente del
-- archivo CSV que consume Power BI, de modo que el tablero no tenga
-- que rehacer el modelo de datos.
-- ---------------------------------------------------------------------
CREATE VIEW v_ventas_plano AS
SELECT
    v.id_venta,
    v.folio,
    date(v.fecha)                        AS fecha,
    v.cliente,
    v.forma_pago,
    p.clave_interna,
    p.descripcion,
    c.nombre                             AS categoria,
    pr.nombre                            AS proveedor,
    COALESCE(up.nombre, u.nombre)        AS presentacion,
    d.cantidad,
    d.cantidad_base,
    d.precio_unitario,
    d.importe,
    p.costo_unitario,
    d.importe - (d.cantidad_base * p.costo_unitario) AS utilidad_estimada
FROM venta_detalle d
JOIN venta    v ON v.id_venta    = d.id_venta
JOIN producto p ON p.id_producto = d.id_producto
JOIN unidad   u ON u.id_unidad   = p.id_unidad
LEFT JOIN categoria    c    ON c.id_categoria       = p.id_categoria
LEFT JOIN proveedor    pr   ON pr.id_proveedor      = p.id_proveedor
LEFT JOIN presentacion pres ON pres.id_presentacion = d.id_presentacion
LEFT JOIN unidad       up   ON up.id_unidad         = pres.id_unidad;
