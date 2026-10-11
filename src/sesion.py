# -*- coding: utf-8 -*-
"""
Quién está usando el sistema.

Hoy el sistema no distingue entre las tres personas del depósito, así
que toda operación se guarda como 'sin identificar'. Ese valor es la
verdad y no un relleno: nadie se identificó.

Este módulo existe para que el día que haya control de acceso solo haya
que cambiar un archivo. El resto del código ya pregunta aquí quién es
el usuario, en lugar de escribir un nombre fijo en cada consulta.

La decisión de cómo se van a separar los accesos quedó para el final
del proyecto, cuando el sistema esté completo. Lo que no podía esperar
era guardar la columna, porque un histórico sin autor no se reconstruye
después.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""

SIN_IDENTIFICAR = 'sin identificar'

# El usuario de la sesión en curso. Se guarda en el módulo y no en la
# sesión de Streamlit porque el repositorio no debe depender de la
# interfaz: los scripts de carga y las pruebas también escriben en la
# base y no tienen pantalla.
_usuario = SIN_IDENTIFICAR


def usuario_actual() -> str:
    """Devuelve quién está operando el sistema."""
    return _usuario


def identificar(nombre: str) -> None:
    """
    Deja registrado quién está operando.

    Todavía no se llama desde ninguna pantalla. Queda lista para cuando
    exista el control de acceso.
    """
    global _usuario
    nombre = (nombre or '').strip()
    _usuario = nombre if nombre else SIN_IDENTIFICAR


def cerrar() -> None:
    """Olvida al usuario identificado."""
    global _usuario
    _usuario = SIN_IDENTIFICAR
