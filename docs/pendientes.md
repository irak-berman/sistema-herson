# Pendientes técnicos

Sistema de control de inventario y análisis de ventas
Depósito Dental HERSON

Asuntos abiertos del desarrollo, ordenados por la fecha en que dejan de
poder esperar. Cada uno dice qué es, por qué importa y cuánto cuesta,
para decidir con información y no por lo que se vea más urgente ese día.

Esta lista se actualiza conforme se cierran cosas. También es la
materia prima de los avances que se entregan a la universidad, donde
hay que reportar qué falta y qué riesgos existen.

Última revisión: 11 de octubre de 2026

---

## Antes de la carga inicial, 13 de noviembre

### Script de respaldo de la base de datos

Sin hacer. Media hora con pruebas.

El sistema completo vive en `basedatos/herson.db`. El repositorio no
contiene ese archivo porque los datos del negocio están excluidos a
propósito, así que hoy no existe ninguna copia.

La fecha no es arbitraria. A partir de la carga inicial, esa base
contiene varios días de corrección del catálogo que no se pueden
reconstruir. Perderla en noviembre no cuesta ventas, que todavía no
hay, cuesta todo el trabajo de limpieza.

El respaldo debe usar la función `backup()` de `sqlite3` y no una copia
de archivo. La base opera en modo WAL, lo que significa que las
escrituras recientes pueden estar todavía en `herson.db-wal`. Copiar el
archivo con el explorador mientras el sistema está abierto puede
producir una copia incompleta sin que nada lo advierta, y eso se
descubre el día que se necesita.

Incluye probar una restauración, no solo que la copia se cree. Una
copia que nunca se restauró es una suposición.

### Corrección del archivo de inventario

En proceso. Es el bloque grande que sigue.

El diagnóstico encontró que 37 por ciento de los 1,553 renglones
requiere corrección antes de poder cargarse. Son 248 renglones sin
clave, 75 claves repetidas en 316 filas y 10 por ciento con la cantidad
escrita como texto.

Hay que decidir qué se corrige automáticamente y qué a mano, y dejar
constancia del criterio, porque esa decisión se reporta en el avance.

---

## Antes de la puesta en operación, 3 de diciembre

### Exportación del archivo plano para Power BI

Sin hacer. Una o dos horas.

Es el camino que se definió desde el principio. El sistema exporta un
archivo plano desde la vista `v_ventas_plano` y Power BI lo lee con su
conector nativo, sin controlador ODBC ni costo de licencia.

Hoy la vista existe y entrega lo que debe, pero nada la exporta. Sin
esto no hay tablero, y el tablero es el segundo entregable del
proyecto.

Falta definir dónde se guarda el archivo y con qué frecuencia se
regenera, que es lo que determina qué tan al día está el tablero.

### Pantalla de créditos pendientes

Sin hacer. Una hora.

El sistema permite vender a crédito y la consulta que lista los
créditos sin liquidar ya existe en `repositorio.py`, igual que la
función para marcarlos como pagados. Lo que no existe es la pantalla.

En este momento una venta a crédito se puede registrar pero nunca se
puede marcar como pagada, así que el saldo del cliente crece para
siempre. Es un hueco funcional, no una mejora.

### Alertas de caducidad y punto de reorden

Hecho. Se muestran en la pantalla de inicio.

Queda pendiente confirmar con el propietario si 180 días de aviso de
caducidad es el plazo correcto una vez que opere con datos reales.

---

## El día de la instalación en el depósito

La lista completa está en `docs/instalacion.md`. Aquí solo lo que se
olvida con más facilidad.

### Cambiar el detalle de errores

En `.streamlit/config.toml`, cambiar `showErrorDetails` de `"full"` a
`"none"`.

Dejarlo en `full` significa que ante cualquier falla el personal ve en
pantalla un rastro técnico de Python, con rutas de archivos y nombres
de funciones internas. Es incomprensible para quien usa el sistema y
expone su estructura a cualquiera que esté frente al monitor,
incluyendo clientes.

### Confirmar los datos de la computadora del depósito

Tres cosas que todavía se desconocen y que cambian el procedimiento de
instalación.

1. Versión de Windows y si es de 64 bits
2. Si tiene Python instalado y en qué versión
3. Si tiene internet durante la instalación

La tercera decide si las dependencias se instalan desde la red o hay
que llevarlas descargadas en una memoria USB. Verificarlas antes ahorra
un viaje en falso.

### Acordar el respaldo externo con el propietario

Una copia automática en la misma computadora protege contra borrado
accidental, pero no contra que falle el disco. Para eso hace falta una
copia fuera de esa computadora, y hay que acordar con qué medio y con
qué frecuencia.

---

## Antes de cerrar el proyecto, marzo de 2027

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
