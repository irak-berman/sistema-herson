# -*- coding: utf-8 -*-
"""
Nota de venta en PDF.

El depósito tiene impresora pero prefiere no imprimir: la nota se manda
al cliente como archivo. Por eso el documento se arma para leerse en un
teléfono y no para pegarse en un talonario.

Se usa fpdf2 y no otra biblioteca por tres razones. Es Python puro, así
que se instala sin compilar nada y no depende de que existan versiones
preparadas para cada versión del intérprete. No necesita programas
externos ni conexión, que son las dos condiciones del proyecto. Y sus
tipografías incluidas cubren el alfabeto latino, de modo que no hay que
cargar archivos de fuentes junto con el sistema.

Esa última decisión tiene una consecuencia: el documento solo puede
contener caracteres del alfabeto latino básico. Por eso aquí no se usan
el guion largo ni el signo menos tipográfico, que en otras pantallas del
sistema sí aparecen.

La nota no se guarda como archivo. Se arma en el momento a partir de la
base, de modo que volver a generarla siempre da el mismo resultado y no
se acumula una carpeta de documentos que después hay que respaldar.

Autor: Irak Berman Gutiérrez
Estadía profesional, Ingeniería en Sistemas Computacionales, UVEG
"""
import io
from functools import lru_cache
from pathlib import Path

from fpdf import FPDF
from PIL import Image

import repositorio as repo

# ---------------------------------------------------------------------
# Datos del negocio
#
# Es el domicilio donde opera el depósito, no el fiscal. La nota la lee
# el cliente, que necesita saber a dónde volver.
#
# No lleva RFC a propósito. El propietario lo pidió así: quien requiere
# factura la solicita aparte y esta nota no la sustituye.
# ---------------------------------------------------------------------
NEGOCIO = 'Deposito Dental HERSON'

# El bloque se corta a proposito en tres renglones. Dejado como una
# sola cadena larga, el salto cae donde quepa y parte el nombre de la
# ciudad a la mitad.
DATOS_NEGOCIO = (
    'Calle 10 #216 esq. 20 de Noviembre, Local 3\n'
    'Col. Cazones, C.P. 93230, Poza Rica, Ver.   |   Tel. 782 348 76 13\n'
    'Lunes a viernes de 9:00 a 14:00 y de 15:00 a 18:00   |   '
    'Sabados de 9:00 a 15:00'
)
LEYENDA = 'No se aceptan devoluciones.'

RAIZ = Path(__file__).resolve().parent.parent
RUTA_LOGO = RAIZ / 'recursos' / 'logo_herson.png'

# Media carta horizontal. El ancho alcanza para la descripción completa
# del producto sin partirla en dos renglones, que es lo que vuelve
# ilegible una nota en la pantalla de un teléfono.
ANCHO = 216
ALTO = 140
MARGEN = 12

AZUL = (43, 44, 107)
GRIS = (91, 100, 120)
LINEA = (210, 214, 226)

# Anchos de cada columna de la tabla, en milimetros. Suman el ancho
# util de la hoja.
#
# La nota no desglosa el descuento por renglon y muestra el importe sin
# rebajar. El sistema sí guarda el descuento renglon por renglon, porque
# lo necesita para medir el margen por producto, pero cuando la rebaja
# se concedio sobre el total de la nota el reparto proporcional produce
# cifras que al cliente no le dicen nada: una nota con 150 pesos de
# descuento acaba mostrando 4.61 en un renglon y 139.80 en otro, y la
# pregunta obvia es de donde salieron esos centavos. En el papel se lee
# mejor lo de siempre: cada producto a su precio, y la rebaja completa
# una sola vez al final.
COLUMNAS = (20, 26, 94, 26, 26)
TITULOS = ('Cantidad', 'Presentacion', 'Descripcion', 'Precio', 'Importe')

FORMAS = {'efectivo': 'Efectivo',
          'transferencia': 'Transferencia',
          'credito': 'Credito'}


@lru_cache(maxsize=1)
def logotipo():
    """
    Devuelve el logotipo reducido al tamano con que se imprime.

    El archivo de recursos mide 917 pixeles de ancho porque sirve para
    la pantalla. Incrustado tal cual, pesa mas que el resto de la nota
    junta y cada documento sale cerca de 100 KB. Reducido a la medida
    en que realmente se ve, con holgura para impresion, la nota baja a
    una fraccion de eso, que importa porque estas notas se mandan por
    WhatsApp una por una.

    El resultado se conserva en memoria: el logotipo es el mismo en
    todas las notas y no tiene caso recalcularlo en cada venta.
    """
    if not RUTA_LOGO.exists():
        return None

    imagen = Image.open(RUTA_LOGO)
    # 13 mm de alto a 300 puntos por pulgada son unos 154 pixeles.
    alto = 160
    ancho = round(imagen.width * alto / imagen.height)
    imagen = imagen.convert('RGB').resize((ancho, alto), Image.LANCZOS)

    memoria = io.BytesIO()
    imagen.save(memoria, format='PNG', optimize=True)
    memoria.seek(0)
    return memoria


def dinero(cantidad: float) -> str:
    """Formatea un importe con separador de miles y dos decimales."""
    return f'$ {cantidad:,.2f}'


def sin_acentos(texto: str) -> str:
    """
    Deja el texto dentro del alfabeto que admiten las tipografias
    incluidas en fpdf2.

    Los nombres de los productos vienen del catalogo y pueden traer
    cualquier caracter. Si uno se sale del alfabeto latino, la
    generacion falla y el usuario se queda sin su nota, que es peor que
    perder un acento.
    """
    if texto is None:
        return ''
    try:
        texto.encode('latin-1')
        return texto
    except UnicodeEncodeError:
        return texto.encode('latin-1', 'replace').decode('latin-1')


class Nota(FPDF):
    """Hoja de la nota, con su encabezado y su pie fijos."""

    def __init__(self):
        super().__init__(orientation='L', unit='mm', format=(ALTO, ANCHO))
        self.set_margins(MARGEN, MARGEN, MARGEN)
        # El pie se dibuja solo, asi que el cuerpo debe detenerse antes.
        self.set_auto_page_break(auto=True, margin=22)

    def header(self) -> None:
        """Logotipo y datos del negocio, en todas las hojas."""
        arriba = self.get_y()
        marca = logotipo()

        if marca is not None:
            marca.seek(0)
            self.image(marca, x=MARGEN, y=arriba, h=13)
            self.set_xy(MARGEN + 42, arriba)
        else:
            # Sin el archivo del logotipo la nota sale igual, con el
            # nombre escrito. Una nota sin membrete sigue sirviendo.
            self.set_xy(MARGEN, arriba)
            self.set_font('helvetica', 'B', 15)
            self.set_text_color(*AZUL)
            self.cell(60, 7, NEGOCIO, new_x='LMARGIN', new_y='NEXT')
            self.set_xy(MARGEN + 42, arriba)

        self.set_font('helvetica', '', 7.5)
        self.set_text_color(*GRIS)
        ancho_datos = ANCHO - MARGEN - (MARGEN + 42) - 46
        self.multi_cell(ancho_datos, 3.6, DATOS_NEGOCIO, align='L')

        self.set_y(arriba)
        self.set_x(ANCHO - MARGEN - 46)
        self.set_font('helvetica', 'B', 9)
        self.set_text_color(*AZUL)
        self.cell(46, 5, 'NOTA DE VENTA', align='R',
                  new_x='LMARGIN', new_y='NEXT')

        self.set_y(max(self.get_y(), arriba + 15))
        self.set_draw_color(*AZUL)
        self.set_line_width(0.5)
        self.line(MARGEN, self.get_y(), ANCHO - MARGEN, self.get_y())
        self.ln(3)

    def footer(self) -> None:
        """Leyenda del negocio y numero de hoja."""
        self.set_y(-18)
        self.set_draw_color(*LINEA)
        self.set_line_width(0.2)
        self.line(MARGEN, self.get_y(), ANCHO - MARGEN, self.get_y())

        self.ln(1.5)
        self.set_font('helvetica', 'B', 8)
        self.set_text_color(*GRIS)
        self.cell(0, 4, LEYENDA, align='C', new_x='LMARGIN', new_y='NEXT')

        self.set_font('helvetica', '', 6.5)
        self.cell(0, 3.5, 'Gracias por su compra.', align='C',
                  new_x='LMARGIN', new_y='NEXT')

        # El numero de hoja solo aparece cuando hay mas de una, para que
        # una nota de tres renglones no diga "Hoja 1 de 1".
        if self.pages_count > 1:
            self.set_font('helvetica', '', 6.5)
            self.cell(0, 3, f'Hoja {self.page_no()} de {{nb}}', align='R')


def _datos_de_la_nota(pdf: Nota, venta) -> None:
    """Folio, fecha, cliente y forma de pago."""
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(*AZUL)
    pdf.cell(28, 5, f'Folio {venta["folio"]}')

    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(42, 5, sin_acentos(venta['fecha'][:16]))

    cliente = (venta['cliente'] or '').strip() or 'Publico en general'
    pdf.cell(13, 5, 'Cliente:')
    pdf.set_font('helvetica', 'B', 9)
    pdf.cell(77, 5, sin_acentos(cliente))

    pdf.set_font('helvetica', '', 9)
    pdf.cell(0, 5, FORMAS.get(venta['forma_pago'], venta['forma_pago']),
             align='R', new_x='LMARGIN', new_y='NEXT')

    if venta['forma_pago'] == 'credito' and not venta['credito_pagado']:
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(179, 38, 30)
        pdf.cell(0, 4, 'PENDIENTE DE PAGO', new_x='LMARGIN', new_y='NEXT')

    if venta['cancelada']:
        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(179, 38, 30)
        pdf.cell(0, 6, 'NOTA CANCELADA', align='C',
                 new_x='LMARGIN', new_y='NEXT')

    pdf.ln(2)


def _encabezado_tabla(pdf: Nota) -> None:
    """Titulos de las columnas."""
    pdf.set_font('helvetica', 'B', 7.5)
    pdf.set_text_color(*GRIS)
    pdf.set_fill_color(244, 245, 250)
    for ancho, titulo, alineacion in zip(
            COLUMNAS, TITULOS, ('C', 'L', 'L', 'R', 'R')):
        pdf.cell(ancho, 6, titulo, align=alineacion, fill=True)
    pdf.ln()


def _renglones(pdf: Nota, detalle: list) -> None:
    """Un renglon por producto vendido."""
    pdf.set_text_color(30, 30, 30)
    pdf.set_draw_color(*LINEA)
    pdf.set_line_width(0.1)

    for renglon in detalle:
        # Si la hoja se acaba a media tabla, la siguiente repite los
        # titulos. Una columna de numeros sin encabezado no se entiende.
        if pdf.will_page_break(6):
            pdf.add_page()
            _encabezado_tabla(pdf)
            pdf.set_text_color(30, 30, 30)

        y = pdf.get_y()
        descripcion = sin_acentos(renglon['descripcion'])

        pdf.set_font('helvetica', '', 8)
        pdf.cell(COLUMNAS[0], 6, f'{renglon["cantidad"]:g}', align='C')
        pdf.cell(COLUMNAS[1], 6, sin_acentos(renglon['presentacion']))

        # La descripcion se recorta si no cabe, en lugar de empujar las
        # columnas de dinero fuera de su lugar.
        while (pdf.get_string_width(descripcion) > COLUMNAS[2] - 2
               and len(descripcion) > 4):
            descripcion = descripcion[:-2]
        pdf.cell(COLUMNAS[2], 6, descripcion)

        pdf.cell(COLUMNAS[3], 6, dinero(renglon['precio_unitario']),
                 align='R')
        # El importe va sin rebajar. El descuento se presenta completo
        # al pie, no repartido entre los renglones.
        pdf.set_font('helvetica', 'B', 8)
        pdf.cell(COLUMNAS[4], 6, dinero(renglon['importe_bruto']),
                 align='R')
        pdf.ln()

        pdf.line(MARGEN, y + 6, ANCHO - MARGEN, y + 6)


def _totales(pdf: Nota, venta, detalle: list) -> None:
    """Importe sin descuento, descuento y total."""
    bruto = round(sum(r['importe_bruto'] for r in detalle), 2)
    rebaja = round(sum(r['descuento'] for r in detalle), 2)
    etiqueta = sum(COLUMNAS[:4]) - 30
    valor = COLUMNAS[4] + 30

    pdf.ln(1)

    # Las dos primeras lineas solo aparecen cuando hubo descuento. En
    # una nota sin rebaja, repetir el mismo numero tres veces confunde.
    if rebaja:
        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(*GRIS)
        pdf.cell(etiqueta, 5, 'Importe sin descuento', align='R')
        pdf.cell(valor, 5, dinero(bruto), align='R', new_x='LMARGIN',
                 new_y='NEXT')
        pdf.cell(etiqueta, 5, 'Descuento', align='R')
        pdf.cell(valor, 5, '- ' + dinero(rebaja), align='R',
                 new_x='LMARGIN', new_y='NEXT')

    pdf.set_font('helvetica', 'B', 12)
    pdf.set_text_color(*AZUL)
    pdf.cell(etiqueta, 8, 'TOTAL', align='R')
    pdf.cell(valor, 8, dinero(venta['total']), align='R',
             new_x='LMARGIN', new_y='NEXT')

    if (venta['observaciones'] or '').strip():
        pdf.ln(1)
        pdf.set_font('helvetica', '', 7.5)
        pdf.set_text_color(*GRIS)
        pdf.multi_cell(0, 3.5,
                       sin_acentos(venta['observaciones'].strip()))


def generar(id_venta: int) -> bytes:
    """
    Arma la nota de una venta y la devuelve como PDF.

    Entrega los bytes y no un archivo, para que la pantalla pueda
    ofrecerla como descarga sin dejar basura en el disco.
    """
    venta = repo.obtener_venta(id_venta)
    if venta is None:
        raise ValueError(f'No existe la venta {id_venta}')

    detalle = repo.detalle_de_venta(id_venta)
    if not detalle:
        raise ValueError(f'La venta {venta["folio"]} no tiene renglones')

    pdf = Nota()
    pdf.set_title(f'Nota {venta["folio"]} - {NEGOCIO}')
    pdf.set_author(NEGOCIO)
    pdf.add_page()

    _datos_de_la_nota(pdf, venta)
    _encabezado_tabla(pdf)
    _renglones(pdf, detalle)
    _totales(pdf, venta, detalle)

    return bytes(pdf.output())


def nombre_de_archivo(folio: str) -> str:
    """Nombre con el que se descarga la nota."""
    return f'Nota {folio} HERSON.pdf'
