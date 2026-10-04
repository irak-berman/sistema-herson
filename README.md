# Sistema de control de inventario y análisis de ventas

Sistema de escritorio para un depósito dental que opera sin control
digital de inventario. Desarrollado como proyecto de estadía profesional
de Ingeniería en Sistemas Computacionales.

## El problema

El negocio lleva su inventario en un libro de Excel con una hoja por
proveedor, donde solo se suma y se resta la cantidad vendida. Las ventas
se documentan en notas escritas a mano que no se capturan en ningún medio
digital.

El diagnóstico sobre el archivo real encontró lo siguiente en un catálogo
de 1,553 renglones.

- 16 % de los renglones sin clave de producto
- 20 % con claves repetidas entre proveedores
- 10 % con la cantidad escrita como texto en lugar de número
- Ninguna columna para registrar lote ni fecha de caducidad
- 37 % de los renglones requiere corrección antes de poder cargarse

Como consecuencia, el negocio no puede saber qué productos están por
caducar, no tiene punto de reorden y no puede analizar su comportamiento
de ventas.

## La solución

Un sistema local que registra cada movimiento en el momento en que
ocurre, alerta sobre caducidades próximas y alimenta un tablero de
indicadores.

Tres restricciones definieron el diseño. Debe operar en una sola
computadora con Windows, sin conexión a internet y sin costo de licencias
para el negocio.

## Stack

- **SQLite** como motor de base de datos, sin servidor y en un solo archivo
- **Python** para la aplicación, con la biblioteca estándar y pandas
- **Streamlit** para la interfaz, servida en localhost
- **Power BI Desktop** para el tablero, alimentado por un archivo plano
- **Mermaid** para el diagrama entidad-relación, versionado como código

## Modelo de datos

Ocho entidades y cuatro vistas. El diagrama completo está en
[docs/modelo-datos.md](docs/modelo-datos.md), junto con la justificación
de cada decisión de diseño.

Tres decisiones vale la pena destacar.

**La existencia se calcula, no se almacena.** No hay columna de
existencia en la tabla de producto. El dato se obtiene sumando los
movimientos, lo que permite explicar en todo momento por qué hay lo que
hay. Guardarla como campo fijo reproduciría el problema que ya tiene el
archivo de Excel.

**Las presentaciones resuelven el mayoreo y el menudeo.** El negocio
vende el mismo producto por caja y por pieza. Un factor de conversión
indica cuántas unidades base entrega cada presentación, de modo que la
venta de una caja descuente las piezas que contiene.

**La clave interna sustituye a la del proveedor.** Como cada proveedor
usa su propia nomenclatura y el mismo código puede pertenecer a productos
distintos, usar esas claves como llave primaria rechazaría uno de cada
cinco renglones en la carga inicial.

## Estructura

```
basedatos/   esquema SQL y script de creación de la base
docs/        documentación del modelo y diagrama entidad-relación
datos/       archivos del negocio (excluidos del repositorio)
src/         código de la aplicación
```

## Cómo crear la base de datos

Requiere Python 3.10 o superior. No hay dependencias que instalar, porque
SQLite viene incluido en la biblioteca estándar.

```bash
python basedatos/crear_base.py
```

El script genera la base, lista los objetos creados y verifica la
integridad del archivo. La base de datos no se versiona: se reconstruye
desde el esquema, que es la fuente de verdad del modelo.

## Estado

Proyecto en desarrollo, de agosto de 2026 a marzo de 2027.

- [x] Diagnóstico del proceso actual y levantamiento de requerimientos
- [x] Diseño del modelo de datos
- [ ] Módulo de catálogo, existencias y registro de ventas
- [ ] Carga inicial del catálogo
- [ ] Pruebas y puesta en operación
- [ ] Alertas de caducidad y punto de reorden
- [ ] Tablero de análisis de ventas
- [ ] Documentación y capacitación

## Nota sobre los datos

El repositorio no contiene información del negocio. El archivo de
inventario, la base de datos generada y cualquier exportación están
excluidos mediante `.gitignore`.

## Autor

Irak Berman Gutiérrez
[GitHub](https://github.com/irak-berman) ·
[LinkedIn](https://linkedin.com/in/irakberman)
