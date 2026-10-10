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

RAIZ = CARPETA_SRC.parent
RUTA_LOGO = RAIZ / 'recursos' / 'logo_herson.png'
RUTA_ICONO = RAIZ / 'recursos' / 'icono_herson.png'

st.set_page_config(
    page_title='Depósito Dental HERSON',
    page_icon=str(RUTA_ICONO) if RUTA_ICONO.exists() else '🦷',
    layout='wide',
)

# El logotipo encabeza la barra lateral. Se comprueba que exista para
# que una carpeta de recursos incompleta no impida arrancar el sistema.
if RUTA_LOGO.exists():
    st.logo(str(RUTA_LOGO))

# ---------------------------------------------------------------------
# Ajustes visuales
#
# Se concentran aquí, y no en cada pantalla, para que las que falten por
# construir los hereden sin volver a definirlos.
# ---------------------------------------------------------------------
ESTILOS = """
<style>
    /* ----- Identidad ----- */

    /* El logotipo lleva texto, por lo que necesita más altura que el
       valor por omisión de Streamlit, pensado para un símbolo cuadrado. */
    [data-testid="stLogo"] {
        height: 2.9rem;
        width: auto;
        margin: 0.5rem 0 0.4rem 0.1rem;
    }

    /* Elementos propios de Streamlit que delatan la herramienta y no
       aportan nada al personal del depósito. */
    [data-testid="stDecoration"] { display: none; }
    [data-testid="stToolbar"] { visibility: hidden; }

    /* ----- Ritmo vertical y tipografía ----- */

    /* El título de página ocupaba casi un tercio de la ventana. En una
       herramienta de trabajo el usuario ya sabe en qué sección está,
       porque el menú lateral se lo indica: lo primero que necesita ver
       son los datos. El ancho máximo evita líneas de texto demasiado
       largas en monitores grandes. */
    .block-container {
        padding-top: 1.9rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    h1 {
        font-size: 1.65rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em;
        padding-top: 0 !important;
        padding-bottom: 0.3rem !important;
    }
    h2 { font-size: 1.25rem !important; font-weight: 600 !important; }
    h3 { font-size: 1.05rem !important; font-weight: 600 !important; }

    /* ----- Indicadores ----- */

    /* Cada indicador se presenta como una tarjeta, de modo que la cifra
       quede visualmente unida a su etiqueta en lugar de flotar sobre el
       fondo. El tamaño del valor permite mostrar importes de siete
       dígitos sin que se recorten. */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E4E7F0;
        border-radius: 10px;
        padding: 0.85rem 1rem;
    }
    [data-testid="stMetricLabel"] p {
        font-size: 0.82rem !important;
        color: #5B6478;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: 600;
    }

    /* ----- Controles ----- */

    /* Los botones de incremento de los campos numéricos estorban al
       capturar precios y cantidades. */
    [data-testid="stNumberInputStepUp"],
    [data-testid="stNumberInputStepDown"] { display: none; }

    .stButton button,
    .stFormSubmitButton button {
        border-radius: 8px;
        font-weight: 500;
    }

    /* ----- Agrupadores ----- */

    [data-testid="stExpander"] {
        border: 1px solid #E4E7F0;
        border-radius: 10px;
    }

    [data-testid="stForm"] {
        border: 1px solid #E4E7F0;
        border-radius: 10px;
    }

    /* El recuadro de foco de las pestañas se oculta cuando llegó por el
       ratón y se conserva cuando llegó por teclado, para no dejar sin
       referencia a quien navegue con el tabulador. */
    button[data-baseweb="tab"]:focus:not(:focus-visible),
    button[data-baseweb="tab"]:active {
        outline: none !important;
        box-shadow: none !important;
    }

    /* ----- Barra lateral ----- */

    [data-testid="stSidebar"] {
        border-right: 1px solid #E4E7F0;
    }
</style>
"""
st.markdown(ESTILOS, unsafe_allow_html=True)

# ---------------------------------------------------------------------
# Navegación
#
# Las secciones son páginas del menú lateral y no pestañas. El menú
# permanece visible al desplazarse, de modo que en listados largos no
# haya que regresar al inicio para cambiar de sección.
#
# Los iconos provienen del conjunto Material Symbols que Streamlit trae
# incluido. Se prefieren a los emoji porque comparten trazo y peso entre
# sí, y porque cada equipo dibuja los emoji a su manera.
# ---------------------------------------------------------------------
PANTALLAS = {
    'General': [
        st.Page('paginas/inicio.py', title='Inicio',
                icon=':material/space_dashboard:', default=True),
    ],
    'Catálogo': [
        st.Page('paginas/cat_buscar.py', title='Buscar',
                icon=':material/search:'),
        st.Page('paginas/cat_alta.py', title='Dar de alta',
                icon=':material/add_circle:'),
        st.Page('paginas/cat_editar.py', title='Editar',
                icon=':material/edit:'),
        st.Page('paginas/cat_apoyo.py', title='Catálogos de apoyo',
                icon=':material/category:'),
    ],
    'Inventario': [
        st.Page('paginas/entradas.py', title='Recepción',
                icon=':material/move_to_inbox:'),
        st.Page('paginas/movimientos.py', title='Movimientos',
                icon=':material/receipt_long:'),
    ],
}

navegacion = st.navigation(PANTALLAS)

with st.sidebar:
    st.divider()
    st.caption('Control de inventario y análisis de ventas')

navegacion.run()
