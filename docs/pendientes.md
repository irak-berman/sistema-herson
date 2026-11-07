# Pendientes técnicos

Sistema de control de inventario y análisis de ventas
Depósito Dental HERSON

Asuntos abiertos del desarrollo, ordenados según la actividad del
cronograma a la que pertenecen. Cada uno dice qué es, por qué importa y
cuánto cuesta, para decidir con información y no por lo que se vea más
urgente ese día.

Las fechas provienen del diagrama de Gantt entregado y firmado. Ningún
pendiente de esta lista puede moverlas: si algo no cabe en su periodo,
se reporta en el avance correspondiente, no se recorre el cronograma.

Esta lista también es materia prima de los avances que se entregan a la
universidad, donde hay que reportar qué falta y qué riesgos existen.

Última revisión: 7 de noviembre de 2026

---

## Actividad 3, del 2 de octubre al 2 de noviembre

Desarrollo del módulo de catálogo, control de existencias por lote y
registro de ventas con generación de notas.

**Terminada el 11 de octubre, con tres semanas de holgura.**

Los cuatro componentes que nombra el entregable están construidos y
probados. Registro y consulta de productos, lotes, movimientos y
emisión de la nota de venta.

La evidencia también quedó levantada. Diez capturas de las pantallas en
operación, una nota de venta generada por el sistema y la referencia al
repositorio, todo reunido en
`Evidencias_Entregable_3_HERSON.pdf`.

El recorrido que las produjo sirvió además como prueba funcional del
módulo y dejó dos hallazgos. Uno quedó corregido en el momento, los
acentos faltantes en los encabezados de la nota en PDF. El otro está
abajo, en la actividad 5, porque no es un error sino una decisión que
corresponde al propietario, si el costo de inventario debe llevar IVA.

---

## Actividad 4, del 3 al 13 de noviembre

Carga inicial del catálogo y de las existencias actuales.

### Script de respaldo de la base de datos

**Hecho y probado en la máquina de desarrollo, el 7 de noviembre.**
`basedatos/respaldo.py`, con `basedatos/probar_respaldo.py` al lado.

Usa `sqlite3.Connection.backup()` y no una copia de archivo, porque la
base opera en modo WAL. Está comprobado con datos: con 50 productos
recién escritos y la conexión abierta, una copia del archivo recupera 0
y `backup()` recupera los 50, porque los 50 estaban en 28 KB de
`herson.db-wal` sin volcar.

Tres defectos salieron al correrlo contra el entorno real, los tres de
la misma familia: cosas que en Linux pasan calladas y en Windows
revientan. El listado tronaba con los nombres de las copias que
dejaron las migraciones. La copia heredaba el modo WAL y ensuciaba la
carpeta con archivos `-wal` y `-shm`. Y dos respaldos del mismo segundo
chocaban, porque `Path.rename` no sobrescribe en Windows. Cada uno
tiene ahora su comprobación en `probar_respaldo.py`.

Queda pendiente acordar con el propietario el respaldo externo, que
está más abajo en la actividad 5.

### Verificación del archivo de inventario

**Hecha el 7 de noviembre.** `carga/diagnostico_inventario.py` perfila
el archivo y escribe el reporte, que queda fuera del repositorio porque
lleva descripciones, claves y costos reales.

Las cifras reales son 1,546 renglones con datos en 8 hojas de 9, 245
sin clave, 33 sin descripción, 132 con la cantidad escrita como texto,
224 sin costo y 89 sin precio.

**El diagnóstico anterior se equivocaba en el punto que más asustaba.**
Contaba 75 claves repetidas en 316 filas y las trataba como un solo
problema. No lo son. La primera columna significa cosas distintas según
la hoja: en BORGATTA, MDC y UNISEAL es un código de proveedor, pero en
MOVIDENT, REISIX, ROETGEN y casi toda la hoja grande es una familia.
`ni-ti` aparece 48 veces, `modulos ALI` 46, `acero` 24. Esos no son
duplicados, son productos distintos del mismo tipo, y esa etiqueta
alimenta `categoria`, no la clave del producto.

Códigos de proveedor realmente repetidos hay 6, en 13 renglones. Eso es
una revisión a mano de un rato, no el bloque de días que se temía.

### Corrección y carga

Sin empezar. Es lo que queda de esta actividad.

`carga/normalizar.py` ya resuelve la parte mecánica y tiene 35
comprobaciones con celdas del archivo real. Interpreta los precios con
mayoreo, que es como el depósito registra las presentaciones: de
`$300.00 c/u o 2 X $525.00` saca el unitario y el paquete de 2 en 525.
Sobre el archivo real son 25 renglones con paquete y solo 1 con el
precio ilegible.

Lo que queda para revisión manual es poco: 70 renglones con la cantidad
ilegible y los 13 con código repetido. El resto se automatiza.

Falta escribir `carga/cargar_inventario.py`. Debe usar las funciones de
`src/repositorio.py` y no SQL directo, porque los disparadores que
mantienen cuadrado el total de las notas viven en la base y saltárselos
ya causó un defecto antes. La existencia inicial entra como movimiento
de tipo entrada, nunca como columna.

### Decisión pendiente del propietario

**El proveedor de 1,230 renglones.** La hoja grande se llama
"ALI, ALSER MED, VILLA DE CORTES" y concentra el 80 por ciento del
catálogo, pero solo trae 4 renglones separadores, así que el archivo no
dice de qué proveedor es cada bloque.

Son dos caminos. Que Roberto indique dónde empieza y termina cada
bloque, o cargar esos productos sin proveedor y corregirlos después
desde la pantalla de edición. El campo es opcional en el modelo, de
modo que la carga no se detiene, pero el día del arranque el depósito
vería 1,230 productos sin proveedor.

Es lo único de esta actividad que depende de otra persona, así que
conviene preguntarlo cuanto antes.

---

## Actividad 5, del 13 de noviembre al 3 de diciembre

Pruebas funcionales, corrección de incidencias y puesta en operación.

### Pantalla de créditos pendientes

Sin hacer. Una hora.

El sistema permite vender a crédito y la consulta que lista los
créditos sin liquidar ya existe en `repositorio.py`, igual que la
función para marcarlos como pagados. Lo que no existe es la pantalla.

En este momento una venta a crédito se puede registrar pero nunca se
puede marcar como pagada, así que el saldo del cliente crece para
siempre. Es un hueco funcional y va a salir en cuanto el propietario
pruebe el sistema con casos reales, que es justo lo que pide esta
actividad.

### Confirmar si el costo de inventario debe llevar IVA

Sin resolver. Es decisión del propietario y de su contador, no técnica.
Cambiarla después cuesta minutos. Dejarla sin preguntar cuesta que tres
cifras de decisión estén mal durante meses.

Hoy el sistema guarda el costo con el IVA incluido. La casilla «El
importe incluye IVA» de la pantalla de recepción no resta el impuesto,
indica que el importe capturado ya lo trae, y al desmarcarla el sistema
se lo suma, para llegar en ambos casos a lo que realmente se pagó. Está
programado de forma coherente.

La pregunta es si ese criterio es el correcto. El depósito tiene RFC. Si
acredita el IVA de sus compras, ese 16 por ciento no es costo sino un
saldo a favor, y entonces el costo debería guardarse neto.

Mueve tres cifras que se usan para decidir.

- El valor del inventario de la pantalla de inicio. Con los datos de
  prueba daba 15,181 pesos con IVA y unos 13,087 sin él.
- El margen por pieza, que es con lo que se fija el precio de venta.
- La utilidad estimada de `v_ventas_plano`, que a partir de enero
  alimenta el tablero de Power BI.

Como está hoy el criterio es consistente, siempre que el precio de venta
también incluya IVA, que es lo habitual en una nota a público en
general. Lo que no puede quedar es una cifra con impuesto comparada
contra otra sin él.

### Cambiar el detalle de errores al instalar

En `.streamlit/config.toml`, cambiar `showErrorDetails` de `"full"` a
`"none"`.

Dejarlo en `full` significa que ante cualquier falla el personal ve en
pantalla un rastro técnico de Python, con rutas de archivos y nombres
de funciones internas. Es incomprensible para quien usa el sistema y
expone su estructura a cualquiera que esté frente al monitor,
incluyendo clientes.

### Confirmar la versión de Python del equipo del depósito

Es el único dato del equipo que sigue sin conocerse. Decide si hay que
instalar Python antes de nada o si basta con instalar las dependencias.

El resto ya está documentado y no hace falta volver a preguntarlo. El
cuestionario del 1 de septiembre confirma que el depósito tiene
internet, que se pueden instalar programas sin restricción de
administrador y que la computadora es de uso exclusivo de
administración y de la vendedora. El anexo fotográfico del reporte de
diagnóstico muestra que se trata de una computadora portátil con
Windows 11 Home y 16 GB de memoria.

Como hay internet, las dependencias se descargan en el momento y no
hace falta llevarlas en una memoria USB.

### Acordar el respaldo externo con el propietario

Una copia automática en la misma computadora protege contra borrado
accidental, pero no contra que falle el disco. Para eso hace falta una
copia fuera de esa computadora, y hay que acordar con qué medio y con
qué frecuencia.

La lista completa de la instalación está en `docs/instalacion.md`.

---

## Actividad 6, del 3 al 23 de diciembre

Módulo de alertas de caducidad próxima y cálculo de punto de reorden.

**Adelantada.** Las dos alertas ya se muestran en la pantalla de
inicio, apoyadas en las vistas `v_por_reabastecer` y
`v_caducidad_proxima`.

Queda confirmar con el propietario, ya con datos reales, si los 180
días de aviso de caducidad y el 15 por ciento de existencia mínima
siguen siendo los criterios correctos. Ese ajuste es lo que convierte
una alerta en algo que se atiende y no en algo que se ignora.

---

## Actividad 8, del 12 de enero al 4 de febrero

Construcción del tablero de análisis de ventas.

### Exportación del archivo plano para Power BI

Sin hacer. Una o dos horas. **Debe estar lista antes del 12 de enero**,
porque el entregable de esta actividad depende de ella.

Es el camino que se definió desde el principio. El sistema exporta un
archivo plano desde la vista `v_ventas_plano` y Power BI lo lee con su
conector nativo, sin controlador ODBC ni costo de licencia.

Hoy la vista existe y entrega lo que debe, incluyendo el importe sin
rebajar, el descuento concedido y la utilidad estimada. Lo que falta es
que algo la escriba a un archivo.

Falta definir dónde se guarda y con qué frecuencia se regenera, que es
lo que determina qué tan al día está el tablero.

---

## Antes de cerrar el proyecto, 17 de marzo

### Separación de accesos

Decidido que se hace al final, cuando el sistema esté completo.

En el depósito trabajan tres personas. El propietario autorizó que la
vendedora vea costos y dé de alta productos, así que la separación se
reduce a una sola regla: no puede cambiar el precio al momento de
vender, pero sí conceder descuentos.

La parte del modelo de datos ya está resuelta. Las tablas `movimiento`
y `venta` guardan quién hizo cada operación, hoy con el valor `sin
identificar`, y `src/sesion.py` existe para que el día que haya control
de acceso solo haya que cambiar un archivo.

Lo que falta es decidir el mecanismo. Para un negocio de tres personas,
un NIP de cuatro dígitos que desbloquee las pantallas administrativas
es más proporcionado que un sistema de usuarios con contraseñas, que en
ese tamaño termina en un papelito pegado al monitor.

---

## Para documentar en los avances

### Evolución del modelo de datos

El modelo creció de 8 a 10 tablas durante el desarrollo. Hay que
explicarlo en el Avance 2, con el motivo de cada cambio.

**Tabla `unidad`.** Al probar la pantalla de catálogo se detectó que
una lista de unidades fija en el código impedía al propietario
registrar presentaciones propias del giro, por lo que se incorporó al
modelo como catálogo administrable.

**Tabla `precio_historial`.** Al definir que la vendedora puede
conceder descuentos pero no modificar precios, se detectó que la regla
quedaba sin efecto si el precio del catálogo podía editarse sin dejar
rastro, ya que bastaría con cambiarlo antes de cobrar.

**Columnas de autoría y de cancelación.** Se agregaron antes de que
existieran datos reales, porque un histórico sin autor no se
reconstruye después.

### Defecto corregido en el cálculo de ventas

Vale la pena reportarlo porque muestra el valor de probar.

Una venta cancelada seguía contando como ingreso en la vista que
alimenta el tablero. El encabezado de la nota se ponía en cero, pero el
detalle quedaba intacto y la vista suma el detalle. Una nota de 1,650
pesos cancelada aparecía completa, con su utilidad.

El origen era guardar un estado del negocio dentro de un campo de texto
libre. Se corrigió con una columna propia y un filtro en la vista.
