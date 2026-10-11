# -*- coding: utf-8 -*-
"""
Migración 001. Rastro de quién, descuento por renglón e historial de
precios.

Aplica a una base ya existente tres cambios que el esquema nuevo ya trae
de fábrica, de modo que una base creada antes quede idéntica a una
creada después.

Los tres cambios comparten el mismo motivo. Son baratos ahora y
imposibles después, porque ninguno se puede reconstruir hacia atrás una
vez que hay histórico capturado.

1. Columna usuario en movimiento y en venta.
   Hoy se llena con 'sin identificar'. El día que el sistema distinga
   entre el propietario y la vendedora, el histórico anterior seguirá
   diciendo la verdad en lugar de atribuirle todo a alguien.

2. Columna descuento en venta_detalle.
   El descuento estaba en el encabezado de la nota, donde no se sabe
   sobre qué producto se concedió. El margen por producto es el
   indicador principal del tablero y con el descuento en el encabezado
   sale mal.

3. Tabla precio_historial.
   La regla es que el precio no se cambia al vender, solo se descuenta.
   Sin esta tabla bastaría con editar el precio en el catálogo antes de
   cobrar y no quedaría huella.

La migración puede ejecutarse varias veces sin causar daño. Revisa qué
falta y aplica solo eso.

Uso desde la carpeta del proyecto:
    python basedatos/migracion_001.py

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_BASE = RAIZ_PROYECTO / 'basedatos' / 'herson.db'
CARPETA_RESPALDOS = RAIZ_PROYECTO / 'basedatos' / 'respaldos'


# =====================================================================
# Definición de la vista
#
# SQLite no sabe modificar una vista: hay que borrarla y volver a
# crearla. La definición se repite aquí porque la migración tiene que
# poder ejecutarse sola, sin leer esquema.sql.
# =====================================================================

VISTA_VENTAS_PLANO = """
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
    v.usuario,
    d.cantidad,
    d.cantidad_base,
    d.precio_unitario,
    (d.cantidad * d.precio_unitario)                 AS importe_bruto,
    d.descuento,
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
LEFT JOIN unidad       up   ON up.id_unidad         = pres.id_unidad
"""

DISPARADORES_TOTALES = [
    """
    CREATE TRIGGER trg_venta_totales_alta
    AFTER INSERT ON venta_detalle
    BEGIN
        UPDATE venta
           SET total     = (SELECT COALESCE(SUM(importe), 0)
                              FROM venta_detalle WHERE id_venta = NEW.id_venta),
               descuento = (SELECT COALESCE(SUM(descuento), 0)
                              FROM venta_detalle WHERE id_venta = NEW.id_venta)
         WHERE id_venta = NEW.id_venta;
    END
    """,
    """
    CREATE TRIGGER trg_venta_totales_cambio
    AFTER UPDATE ON venta_detalle
    BEGIN
        UPDATE venta
           SET total     = (SELECT COALESCE(SUM(importe), 0)
                              FROM venta_detalle WHERE id_venta = NEW.id_venta),
               descuento = (SELECT COALESCE(SUM(descuento), 0)
                              FROM venta_detalle WHERE id_venta = NEW.id_venta)
         WHERE id_venta = NEW.id_venta;
    END
    """,
    """
    CREATE TRIGGER trg_venta_totales_baja
    AFTER DELETE ON venta_detalle
    BEGIN
        UPDATE venta
           SET total     = (SELECT COALESCE(SUM(importe), 0)
                              FROM venta_detalle WHERE id_venta = OLD.id_venta),
               descuento = (SELECT COALESCE(SUM(descuento), 0)
                              FROM venta_detalle WHERE id_venta = OLD.id_venta)
         WHERE id_venta = OLD.id_venta;
    END
    """,
]

TABLA_PRECIO_HISTORIAL = """
CREATE TABLE precio_historial (
    id_historial    INTEGER PRIMARY KEY AUTOINCREMENT,
    id_producto     INTEGER NOT NULL,
    id_presentacion INTEGER,
    campo           TEXT    NOT NULL
                    CHECK (campo IN ('precio_venta', 'costo_unitario')),
    valor_anterior  REAL,
    valor_nuevo     REAL    NOT NULL CHECK (valor_nuevo >= 0),
    fecha           TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    usuario         TEXT    NOT NULL DEFAULT 'sin identificar',
    motivo          TEXT,
    FOREIGN KEY (id_producto)     REFERENCES producto (id_producto),
    FOREIGN KEY (id_presentacion) REFERENCES presentacion (id_presentacion)
)
"""


# =====================================================================
# Apoyo
# =====================================================================


def columnas_de(conexion: sqlite3.Connection, tabla: str) -> set:
    """Nombres de las columnas de una tabla."""
    filas = conexion.execute(f'PRAGMA table_info({tabla})').fetchall()
    return {fila[1] for fila in filas}


def existe_tabla(conexion: sqlite3.Connection, nombre: str) -> bool:
    """Indica si existe una tabla con ese nombre."""
    fila = conexion.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (nombre,)
    ).fetchone()
    return fila is not None


def existe_disparador(conexion: sqlite3.Connection, nombre: str) -> bool:
    """Indica si existe un disparador con ese nombre."""
    fila = conexion.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = ?",
        (nombre,)
    ).fetchone()
    return fila is not None


def respaldar(ruta: Path) -> Path:
    """
    Copia la base antes de modificarla y devuelve la ruta de la copia.

    Se usa la función backup de sqlite3 y no una copia de archivo,
    porque la base opera en modo WAL y las escrituras recientes pueden
    estar todavía en los archivos auxiliares. Copiar el archivo con el
    explorador puede producir una copia incompleta sin avisar.
    """
    CARPETA_RESPALDOS.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    destino = CARPETA_RESPALDOS / f'herson_antes_migracion_001_{marca}.db'

    origen = sqlite3.connect(ruta)
    copia = sqlite3.connect(destino)
    with copia:
        origen.backup(copia)
    copia.close()
    origen.close()
    return destino


# =====================================================================
# Migración
# =====================================================================


def aplicar(ruta: Path = RUTA_BASE) -> None:
    """Aplica los cambios que falten y reporta lo que hizo."""
    if not ruta.exists():
        print(f'No se encontró la base en {ruta}')
        print('Si todavía no existe, ejecute basedatos/crear_base.py,')
        print('que ya crea el esquema nuevo y no necesita esta migración.')
        sys.exit(1)

    conexion = sqlite3.connect(ruta)
    conexion.execute('PRAGMA foreign_keys = OFF')

    # Qué falta
    pendientes = []
    if 'usuario' not in columnas_de(conexion, 'movimiento'):
        pendientes.append('usuario en movimiento')
    if 'usuario' not in columnas_de(conexion, 'venta'):
        pendientes.append('usuario en venta')
    if 'descuento' not in columnas_de(conexion, 'venta_detalle'):
        pendientes.append('descuento en venta_detalle')
    if not existe_tabla(conexion, 'precio_historial'):
        pendientes.append('tabla precio_historial')
    if not existe_disparador(conexion, 'trg_venta_totales_alta'):
        pendientes.append('disparadores de totales de la nota')

    if not pendientes:
        print('La base ya tiene los tres cambios. No hay nada que hacer.')
        conexion.close()
        return

    print('Cambios por aplicar:')
    for cambio in pendientes:
        print(f'  - {cambio}')
    print()

    copia = respaldar(ruta)
    print(f'Respaldo previo: {copia.name}')
    print()

    aplicados = []
    try:
        with conexion:
            if 'usuario' not in columnas_de(conexion, 'movimiento'):
                conexion.execute(
                    "ALTER TABLE movimiento ADD COLUMN usuario TEXT "
                    "NOT NULL DEFAULT 'sin identificar'"
                )
                aplicados.append('movimiento.usuario')

            if 'usuario' not in columnas_de(conexion, 'venta'):
                conexion.execute(
                    "ALTER TABLE venta ADD COLUMN usuario TEXT "
                    "NOT NULL DEFAULT 'sin identificar'"
                )
                aplicados.append('venta.usuario')

            if 'descuento' not in columnas_de(conexion, 'venta_detalle'):
                conexion.execute(
                    'ALTER TABLE venta_detalle ADD COLUMN descuento REAL '
                    'NOT NULL DEFAULT 0 CHECK (descuento >= 0)'
                )
                aplicados.append('venta_detalle.descuento')

            if not existe_tabla(conexion, 'precio_historial'):
                conexion.execute(TABLA_PRECIO_HISTORIAL)
                conexion.execute('CREATE INDEX idx_precio_historial_producto '
                                 'ON precio_historial (id_producto)')
                conexion.execute('CREATE INDEX idx_precio_historial_fecha '
                                 'ON precio_historial (fecha)')
                aplicados.append('precio_historial')

            # La vista se rehace siempre, porque ahora muestra el
            # descuento y el importe sin rebaja.
            conexion.execute('DROP VIEW IF EXISTS v_ventas_plano')
            conexion.execute(VISTA_VENTAS_PLANO)
            aplicados.append('v_ventas_plano')

            # Los disparadores también, para que la definición quede
            # igual que en esquema.sql aunque esta migración se corra
            # sobre una base que ya tenía una versión anterior.
            for nombre in ('trg_venta_totales_alta',
                           'trg_venta_totales_cambio',
                           'trg_venta_totales_baja'):
                conexion.execute(f'DROP TRIGGER IF EXISTS {nombre}')
            for definicion in DISPARADORES_TOTALES:
                conexion.execute(definicion)
            aplicados.append('disparadores de totales de la nota')

            # Las notas ya capturadas se recalculan una sola vez, para
            # que el encabezado cuadre con su detalle desde hoy.
            conexion.execute("""
                UPDATE venta
                   SET total = (SELECT COALESCE(SUM(importe), 0)
                                  FROM venta_detalle
                                 WHERE id_venta = venta.id_venta),
                       descuento = (SELECT COALESCE(SUM(descuento), 0)
                                      FROM venta_detalle
                                     WHERE id_venta = venta.id_venta)
                 WHERE EXISTS (SELECT 1 FROM venta_detalle
                                WHERE id_venta = venta.id_venta)
            """)

    except sqlite3.Error as error:
        conexion.close()
        print(f'La migración falló y no se guardó ningún cambio: {error}')
        print(f'La base quedó como estaba. El respaldo está en {copia}')
        sys.exit(1)

    # Verificación
    conexion.execute('PRAGMA foreign_keys = ON')
    integridad = conexion.execute('PRAGMA integrity_check').fetchone()[0]
    ventas = conexion.execute('SELECT COUNT(*) FROM venta').fetchone()[0]
    movimientos = conexion.execute(
        'SELECT COUNT(*) FROM movimiento').fetchone()[0]
    conexion.close()

    print('Aplicado:')
    for cambio in aplicados:
        print(f'  - {cambio}')
    print()
    print(f'Integridad del archivo: {integridad}')
    print(f'Movimientos conservados: {movimientos}')
    print(f'Ventas conservadas: {ventas}')


if __name__ == '__main__':
    aplicar()
