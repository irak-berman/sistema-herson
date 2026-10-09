# -*- coding: utf-8 -*-
"""
Punto de entrada del sistema de inventario del Depósito Dental HERSON.

Configura la aplicación, aplica los ajustes visuales y arma el menú de
navegación. Cada pantalla vive en su propio archivo dentro de la carpeta
paginas, de modo que agregar una nueva no obligue a tocar las demás.

Uso desde la carpeta del proyecto, con el entorno activado:
    streamlit run src/app.py

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import sys
from pathlib import Path

import streamlit as st

# Streamlit ejecuta el archivo desde la raíz del proyecto, así que la
# carpeta src debe agregarse a la ruta de búsqueda para que las
# pantallas puedan importar los módulos propios.
CARPETA_SRC = Path(__file__).resolve().parent
if str(CARPETA_SRC) not in sys.path:
    sys.path.insert(0, str(CARPETA_SRC))

st.set_page_config(
    page_title='Depósito Dental HERSON',
    page_icon='🦷',
    layout='wide',
)

# Ajustes visuales.
ESTILOS = """
<style>
    /* Botones de incremento de los campos numéricos, que estorban al
       capturar precios y cantidades */
    [data-testid="stNumberInputStepUp"],
    [data-testid="stNumberInputStepDown"] { display: none; }

    [data-testid="stToolbar"] { visibility: hidden; }

    /* Recuadro de foco de las pestañas. Se oculta cuando el foco llegó
       por el ratón y se conserva cuando llegó por teclado, para no
       dejar sin referencia a quien navegue con el tabulador. */
    button[data-baseweb="tab"]:focus:not(:focus-visible),
    button[data-baseweb="tab"]:active {
        outline: none !important;
        box-shadow: none !important;
    }

    /* Los indicadores deben alojar importes de siete dígitos sin
       recortarse, porque el inventario completo del depósito supera
       las seis cifras. */
    [data-testid="stMetricValue"] { font-size: 1.7rem; }

    /* Margen superior reducido. El espacio que Streamlit reserva por
       omisión es para su barra de herramientas, que aquí está oculta. */
    .block-container { padding-top: 2.2rem; }
</style>
"""
st.markdown(ESTILOS, unsafe_allow_html=True)

# Las secciones del catálogo son páginas del menú lateral y no pestañas.
# El menú permanece visible al desplazarse, de modo que en listados
# largos no haya que regresar al inicio para cambiar de sección.
PANTALLAS = {
    'General': [
        st.Page('paginas/inicio.py', title='Inicio', icon='🏠', default=True),
    ],
    'Catálogo': [
        st.Page('paginas/cat_buscar.py', title='Buscar', icon='🔍'),
        st.Page('paginas/cat_alta.py', title='Dar de alta', icon='➕'),
        st.Page('paginas/cat_editar.py', title='Editar', icon='✏️'),
        st.Page('paginas/cat_apoyo.py', title='Catálogos de apoyo', icon='🗂️'),
    ],
    'Inventario': [
        st.Page('paginas/entradas.py', title='Recepción', icon='📥'),
        st.Page('paginas/movimientos.py', title='Movimientos', icon='🧾'),
    ],
}

navegacion = st.navigation(PANTALLAS)

with st.sidebar:
    st.divider()
    st.caption('Depósito Dental HERSON')
    st.caption('Control de inventario')

navegacion.run()
