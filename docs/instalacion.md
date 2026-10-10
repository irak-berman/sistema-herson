# Instalación y puesta en operación

Sistema de control de inventario y análisis de ventas
Depósito Dental HERSON

Esta lista se recorre una sola vez, el día que el sistema se instala en la
computadora del depósito. Cada paso tiene una casilla porque algunos no se
notan si se omiten, en particular el paso 6.

La operación diaria del sistema no requiere internet. La instalación sí
puede requerirlo una vez, según el camino que se siga en el paso 3.

## Antes de ir al depósito

Conviene llevar todo en una memoria USB para no depender de la conexión
del local.

- [ ] Instalador de Python para Windows de 64 bits, la misma versión con la
      que se desarrolló el sistema
- [ ] Carpeta completa del proyecto, incluyendo `recursos/` con los logos
- [ ] Archivo de inventario del negocio ya corregido, listo para la carga
      inicial
- [ ] Memoria USB adicional o disco externo, si se va a dejar configurado
      el respaldo del paso 9

### Datos que hay que confirmar antes

Tres cosas se desconocen de la computadora del depósito y cambian el
procedimiento. Verificarlas antes ahorra un viaje en falso.

1. Versión de Windows y si es de 64 bits
2. Si tiene Python instalado y en qué versión
3. Si tiene internet durante la instalación

## Paso 1. Verificar Python

- [ ] Abrir el símbolo del sistema y ejecutar lo siguiente

```
python --version
```

Si responde con la versión, Python ya está instalado y se continúa al paso
2. Si responde que el comando no se reconoce, hay que instalarlo con el
archivo que se llevó en la USB.

Al correr el instalador es indispensable marcar la casilla **Add python.exe
to PATH** en la primera pantalla. Si no se marca, ningún comando de esta
guía va a funcionar y la causa no es evidente.

- [ ] Volver a ejecutar `python --version` y confirmar que ahora responde

## Paso 2. Copiar el proyecto

- [ ] Copiar la carpeta del proyecto a un lugar estable del disco

Se recomienda `C:\sistema-herson`, no el escritorio ni Descargas ni
Documentos. El escritorio se reorganiza, Descargas se vacía y en Documentos
la ruta cambia si la cuenta tiene OneDrive activo, que es la causa más
común de que un sistema así deje de abrir sin motivo aparente.

- [ ] Confirmar que existe la subcarpeta `recursos` con los dos logos
      dentro y el ícono

## Paso 3. Instalar las dependencias

Hay dos caminos y depende de si la computadora tiene internet.

### Con internet

- [ ] Desde la carpeta del proyecto, ejecutar

```
pip install -r requirements.txt
```

### Sin internet

Las dependencias se descargan antes, en la computadora de desarrollo, y se
llevan en la USB. Las dos computadoras deben tener la misma versión de
Python y la misma arquitectura, porque los paquetes descargados son
binarios compilados para una combinación específica.

En la computadora de desarrollo, antes de ir al depósito

```
pip download -r requirements.txt -d paquetes
```

Ya en el depósito, desde la carpeta del proyecto, con la carpeta
`paquetes` copiada al lado

```
pip install --no-index --find-links paquetes -r requirements.txt
```

- [ ] Verificar que la instalación terminó sin errores

```
python -c "import streamlit, pandas; print('dependencias listas')"
```

## Paso 4. Crear la base de datos

- [ ] Desde la carpeta del proyecto, ejecutar

```
python basedatos/crear_base.py
```

El script genera la base, lista los objetos creados y verifica la
integridad del archivo. Debe reportar las nueve tablas y las cuatro
vistas. Si reporta menos, el esquema se copió incompleto y hay que volver
al paso 2.

La base queda en `basedatos/herson.db`. Ese archivo es el sistema
completo. Todo lo demás se puede reinstalar, ese archivo no.

## Paso 5. Cargar el catálogo inicial

- [ ] Ejecutar la carga del archivo de inventario corregido
- [ ] Comparar el total de productos cargados contra el total esperado
- [ ] Revisar el reporte de renglones rechazados y resolverlos antes de
      continuar

## Paso 6. Cambiar el detalle de errores

Este es el paso que se olvida.

En el archivo `.streamlit/config.toml` existe la siguiente línea, que
durante el desarrollo muestra el error completo en pantalla.

```toml
showErrorDetails = "full"
```

- [ ] Cambiarla por

```toml
showErrorDetails = "none"
```

Dejarla en `full` significa que ante cualquier falla el propietario va a
ver en pantalla un trazo de error de Python, con rutas de archivos y
nombres de funciones internas. Es incomprensible para quien usa el
sistema, da la impresión de que se rompió algo grave y expone la
estructura interna del programa a cualquiera que esté frente al monitor,
incluyendo clientes.

## Paso 7. Acceso directo en el escritorio

- [ ] Clic derecho sobre `iniciar.bat`, enviar al escritorio como acceso
      directo
- [ ] Renombrar el acceso directo a algo claro, por ejemplo **Inventario
      HERSON**
- [ ] Cambiar el ícono del acceso directo por `recursos/icono_herson.png`
      convertido a `.ico`, si se quiere que no se vea como un archivo de
      sistema
- [ ] Explicar que el sistema se cierra con `detener.bat` y no cerrando
      solamente la ventana

Cerrar nada más la ventana del navegador deja el proceso corriendo en
segundo plano. No causa pérdida de datos, pero al día siguiente puede
impedir que el sistema arranque porque el puerto sigue ocupado.

## Paso 8. Prueba de aceptación

No se da por instalado hasta que el recorrido completo funcione en esa
computadora, con el propietario presente y haciéndolo él.

- [ ] Abrir el sistema desde el acceso directo del escritorio
- [ ] Buscar un producto por descripción y por clave
- [ ] Dar de alta un producto nuevo con su presentación
- [ ] Registrar una recepción con factura, con lote y caducidad
- [ ] Verificar que la existencia subió por la cantidad correcta
- [ ] Registrar una venta de menudeo y una de mayoreo del mismo producto
- [ ] Verificar que la existencia bajó según el factor de conversión
- [ ] Generar la nota en PDF y abrirla
- [ ] Corregir una cantidad mal capturada y verificar que queda el ajuste
      registrado
- [ ] Cerrar con `detener.bat` y volver a abrir, confirmando que los datos
      siguen ahí

## Paso 9. Respaldo

El sistema entero vive en un archivo. Si ese archivo se pierde, se pierden
el inventario y el histórico de ventas completos, y no existe copia en el
repositorio porque los datos del negocio están excluidos a propósito por
el compromiso de confidencialidad.

Hay dos riesgos distintos y no se cubren con la misma medida.

**Borrado accidental o captura equivocada.** Se cubre con una copia
automática en la misma computadora, en otra carpeta y con la fecha en el
nombre. Es gratis, no requiere que nadie se acuerde de hacer nada y
permite volver al estado de ayer.

**Falla del disco, robo o pérdida de la computadora.** Solo se cubre con
una copia fuera de esa computadora. Una copia en el mismo disco no sirve
de nada si el disco es el que falla.

Lo recomendable es tener las dos. La automática local como red de
seguridad diaria, y una copia manual a una USB o disco externo con
periodicidad fija.

- [ ] Definir con el propietario dónde se guarda la copia local
- [ ] Definir con el propietario el medio y la frecuencia de la copia
      externa
- [ ] Instalar el script de respaldo y verificar que genera el archivo
- [ ] Probar una restauración, no solo que la copia se cree

Una copia que nunca se restauró no es un respaldo, es una suposición. La
prueba de restauración es parte de la instalación, no un extra.

### Nota técnica sobre el respaldo

La base opera en modo WAL, lo que significa que las escrituras recientes
pueden estar en los archivos auxiliares `herson.db-wal` y `herson.db-shm`
y no todavía dentro de `herson.db`. Por eso el respaldo no debe hacerse
copiando el archivo con el explorador de Windows mientras el sistema está
abierto, porque la copia puede quedar incompleta sin que nada lo
advierta.

El respaldo se hace con la función `backup()` de la biblioteca `sqlite3`,
que produce una copia consistente incluso con el sistema en uso.

## Si algo falla

**El acceso directo no abre nada.** Python no quedó en el PATH. Repetir el
paso 1 con la casilla marcada.

**Dice que el puerto está ocupado.** Quedó un proceso anterior corriendo.
Ejecutar `detener.bat` y volver a intentar.

**Abre pero sin logo.** Falta la carpeta `recursos`. El sistema está
diseñado para arrancar igual sin ella, por eso no marca error.

**Abre pero no hay productos.** La base se creó pero no se cargó el
catálogo. Volver al paso 5.

**Error al guardar un movimiento.** Revisar que la carpeta del proyecto no
esté dentro de una ruta sincronizada con OneDrive. La sincronización puede
bloquear el archivo de la base mientras SQLite intenta escribir.
