# -*- coding: utf-8 -*-
"""
Editar producto.

Las secciones del catálogo son páginas del menú lateral y no pestañas,
para que puedan alcanzarse desde cualquier punto de la pantalla sin
volver al principio del listado.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import streamlit as st

import catalogo_vistas as cv

st.title('Editar producto')

_, _, unidades = cv.cargar_catalogos()
cv.seccion_edicion(unidades)
