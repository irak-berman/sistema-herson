# -*- coding: utf-8 -*-
"""
Catálogos de apoyo.

Las secciones del catálogo son páginas del menú lateral y no pestañas,
para que puedan alcanzarse desde cualquier punto de la pantalla sin
volver al principio del listado.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import streamlit as st

import catalogo_vistas as cv

st.title('Catálogos de apoyo')

cv.cargar_catalogos()

columna_izquierda, columna_derecha = st.columns(2)
with columna_izquierda:
    cv.bloque_proveedores()
    st.divider()
    cv.bloque_unidades()
with columna_derecha:
    cv.bloque_categorias()
