# -*- coding: utf-8 -*-
"""
Buscar productos.

Las secciones del catálogo son páginas del menú lateral y no pestañas,
para que puedan alcanzarse desde cualquier punto de la pantalla sin
volver al principio del listado.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import streamlit as st

import catalogo_vistas as cv

st.title('Buscar productos')

proveedores, categorias, _ = cv.cargar_catalogos()
cv.seccion_busqueda(proveedores, categorias)
