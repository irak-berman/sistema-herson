# Contexto del proyecto

Instrucciones para cualquier asistente que trabaje en este repositorio. Léelas antes de proponer o escribir código.

Sistema de control de inventario y análisis de ventas para el Depósito
Dental HERSON, en Poza Rica, Veracruz. Lo desarrolla Irak Berman
Gutiérrez como estadía profesional de Ingeniería en Sistemas
Computacionales de la UVEG, del 31 de agosto de 2026 al 17 de marzo de
2027.

El depósito controla hoy su inventario en un libro de Excel con una
hoja por proveedor, donde solo se suma y se resta la cantidad vendida.
Las notas de venta se escriben a mano y no se capturan en ningún medio
digital. Son tres personas: el propietario Roberto Herrera García y su
esposa como administradores, y una vendedora.

---

## Reglas que no se negocian

**El sistema opera sin internet y sin costo.** Nada de servicios de
paga, nada de hospedaje, nada que requiera conexión para funcionar.
Corre en la computadora del depósito, una laptop con Windows 11 Home y
16 GB de memoria.

**Los datos del negocio nunca entran al repositorio.** El archivo de
inventario, la base generada, los reportes de diagnóstico y cualquier
exportación están excluidos en `.gitignore`. Hay un compromiso de
confidencialidad firmado. Cualquier evidencia que se publique usa datos
inventados, nunca nombres de clientes ni costos reales.

**Los commits van solo a nombre de Irak.** Sin líneas de coautoría de
Claude ni de ninguna herramienta.

**El respaldo va antes de tocar la base.** `python
basedatos/respaldo.py`. La base opera en modo WAL, así que una copia
del archivo hecha con el explorador puede salir incompleta sin avisar.
Está comprobado: con 50 productos recién escritos, la copia de archivo
recupera 0 y `sqlite3.Connection.backup()` recupera los 50.

**Comentarios y mensajes de commit en español.**

---

## Decisiones de diseño que hay que respetar

**La existencia se calcula, nunca se almacena.** No hay columna de
existencia en `producto`. La existencia de un producto es la suma de
sus movimientos. Si algo parece necesitar una columna de existencia, la
respuesta es una vista, no una columna.

**Un error no se edita, se corrige con un ajuste.** Cambiar la cantidad
de un movimiento no modifica el movimiento original: genera un
movimiento de tipo `ajuste` que lo compensa y queda visible en el
historial.

**La vendedora puede conceder descuentos pero no cambiar precios.** Por
eso el descuento se guarda en su propia columna de `venta_detalle` y
todo cambio de precio o de costo deja rastro en `precio_historial`. Sin
ese rastro la regla sería inaplicable, porque bastaría con cambiar el
precio antes de cobrar.

**Las presentaciones son formas de vender, no de almacenar.** La
existencia se lleva siempre en la unidad base. Una caja de 100 piezas
es una fila de `presentacion` con su factor y su precio; al venderla se
descuentan 100 piezas.

**Nada de `st.form` en pantallas que escriben.** Un formulario de
Streamlit se envía al pulsar Enter en cualquier campo, y eso llegó a
registrar una venta y un alta de producto a medio capturar. Los campos
se vacían cambiándoles la clave, con el helper `ciclo()` de
`catalogo_vistas.py`, porque borrar la clave del estado deja al control
mostrando el valor anterior.

---

## Arquitectura

Por capas, de abajo hacia arriba.

- `basedatos/esquema.sql`, 10 tablas, 4 vistas y 3 disparadores
- `src/conexion.py`, apertura de la base con llaves foráneas y WAL
- `src/repositorio.py`, acceso a datos, una función por operación
- `src/servicios.py`, reglas de negocio y transacciones
- `src/paginas/`, una pantalla de Streamlit por archivo
- `src/catalogo_vistas.py`, componentes compartidos del catálogo
- `src/nota_pdf.py`, generación de la nota de venta
- `src/sesion.py`, costura para el control de acceso que falta

Las notas no se guardan en disco. Se arman desde la base cada vez que
se piden, de modo que una nota recuperada meses después sale idéntica.

Para arrancar: doble clic en `iniciar.bat`, o
`streamlit run src/app.py`.

---

## Dónde va el proyecto

Las fechas vienen del diagrama de Gantt ya entregado y firmado, así que
no se mueven. Si algo no cabe en su periodo se reporta como atraso, no
se recorre el cronograma.

Terminadas: actividad 1, diagnóstico. Actividad 2, modelo de datos.
Actividad 3, módulo de catálogo, lotes y ventas con notas, cerrada el 2
de noviembre.

**En curso: actividad 4, carga inicial del catálogo, del 3 al 13 de
noviembre.** Entregable: script de carga y evidencia de la verificación
de los datos cargados.

Siguen: actividad 5, pruebas y puesta en operación, 13 nov al 3 dic.
Actividad 6, alertas de caducidad y punto de reorden, 3 al 23 dic, ya
adelantada. Actividad 8, tablero de Power BI, 12 ene al 4 feb.

`docs/pendientes.md` tiene el detalle de cada pendiente ordenado por
actividad. Léelo antes de proponer trabajo nuevo.

---

## Lo que ya se sabe del archivo de inventario

Está en `datos/inventario_oficial_deposito_herson.xlsx`, fuera del
repositorio. Nueve hojas, una por proveedor, 1,546 renglones con datos.
`carga/diagnostico_inventario.py` lo perfila y escribe el reporte.

Hallazgos que ya se hicieron y no hace falta repetir.

**La primera columna significa cosas distintas según la hoja.** En
BORGATTA, MDC y UNISEAL es un código de proveedor. En MOVIDENT, REISIX,
ROETGEN y casi toda la hoja grande es una familia: `ni-ti` aparece 48
veces, `modulos ALI` 46, `acero` 24. Esas no son claves repetidas, son
productos distintos del mismo tipo, y esa etiqueta alimenta
`categoria`, no la clave del producto. Códigos de proveedor realmente
repetidos hay 6, en 13 renglones, y esos sí se revisan a mano.

**Los precios con mayoreo vienen como texto.** Por ejemplo
`$300.00 c/u o 2 X $525.00`. `carga/normalizar.py` los interpreta y
saca el unitario y los paquetes, que se vuelven filas de
`presentacion`. Sobre el archivo real son 25 renglones con paquete y
solo 1 con el precio ilegible.

**70 renglones traen la cantidad ilegible** y van a revisión manual.
`carga/normalizar.py` los reporta en lugar de adivinar, a propósito: un
costo mal leído se arrastra a todos los márgenes del negocio.

**Falta decidir el proveedor de 1,230 renglones.** La hoja grande se
llama "ALI, ALSER MED, VILLA DE CORTES" y concentra el 80 por ciento
del catálogo, pero solo trae 4 renglones separadores, así que el
archivo no dice de qué proveedor es cada bloque. Lo tiene que decidir
Roberto. El campo es opcional en el modelo, de modo que la carga puede
proceder sin él.

**La existencia mínima inicial** es el 15 por ciento de la existencia
cargada, redondeado hacia arriba y nunca menor a 1, criterio acordado
con el propietario.

---

## Cómo trabajar aquí

Rama y pull request para cualquier cambio de fondo, no commits directos
a `main`. El historial de decisiones es parte de la evidencia que se
entrega a la universidad.

Prueba antes de subir. `carga/probar_normalizar.py` y
`basedatos/probar_modelo.py` corren sin tocar la base real.

Cuando una decisión dependa del propietario, no la inventes. Dilo y
deja el camino abierto para las dos opciones.
