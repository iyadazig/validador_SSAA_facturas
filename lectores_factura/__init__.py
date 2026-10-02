# -*- coding: utf-8 -*-
"""
Lectores de factura por comercializadora.

Para anadir una comercializadora: crear un modulo con una funcion
`leer(texto) -> DatosFactura` que parta de `lector_generico(texto)` y corrija
los campos con los patrones de su maqueta, registrarla en LECTORES y, si se
puede, anadir su CIF a base.CIF_COMERCIALIZADORAS.
"""

from . import endesa, naturgy
from .base import (DatosFactura, LineaSSAA, lector_generico, texto_pdf,
                   detectar_comercializadora)

# nombre de comercializadora (como en base.COMERCIALIZADORAS) -> funcion leer
LECTORES = {
    "Endesa": endesa.leer,
    "Naturgy": naturgy.leer,
}


def leer_texto(texto):
    comer = detectar_comercializadora(texto)
    if comer in LECTORES:
        f = LECTORES[comer](texto)
        f.comercializadora = comer
        f.lector = comer
    else:
        f = lector_generico(texto)
        if comer:
            f.avisos.append("Aún no hay lector específico para %s: datos leídos con "
                            "el lector genérico." % comer)
    return f


def leer_factura(datos_pdf):
    return leer_texto(texto_pdf(datos_pdf))
