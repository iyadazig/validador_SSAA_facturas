# -*- coding: utf-8 -*-
"""
Naturgy Clientes Empresas (grandes clientes).

Maqueta observada (etiqueta en una linea y valor en la siguiente):
  FACTURA Nº      CUENTA CONTRATO ...      FECHA EMISIÓN ...
  PIxxxxxxxxxxxxxx  xxxxxxxxx              dd.mm.aaaa
  CUPS ES00...    Tarifa ATR: 6.xTD        PERIODO dd.mm.aa / dd.mm.aa
  ENERGÍA ACTIVA P1        10.000 kWh        0,100000       1.000,00 Eur
  REGULARIZACIÓN DE SERVICIOS DE AJUSTE
                           10.000 kWh        0,00500000        50,00 Eur
     dd.mm.aaaa - dd.mm.aaaa
Las regularizaciones de SSAA son de meses anteriores, una linea por mes, cada
una con el consumo de su mes.
"""

import re

from .base import LineaSSAA, comprobar_lineas, fecha_es, lector_generico, numero_es

NUM = r"-?\d[\d.]*(?:,\d+)?"

RE_NUMERO = re.compile(r"FACTURA\s+N[ºo°][^\n]*\n\s*([A-Z]{2}\d{8,})", re.I)
RE_EMISION = re.compile(r"FECHA\s+EMISI[OÓ]N[^\n]*\n\s*(\d{2}\.\d{2}\.\d{4})", re.I)
RE_PERIODO = re.compile(r"\b(\d{2}\.\d{2}\.\d{2})\s*/\s*(\d{2}\.\d{2}\.\d{2})\b")
RE_TARIFA = re.compile(r"Tarifa\s+ATR\s*:\s*([236]\.[0-4]TD(?:VE)?)", re.I)
RE_ENERGIA = re.compile(r"ENERG[IÍ]A\s+ACTIVA\s+P([1-6])\s+(" + NUM + r")\s*kWh", re.I)
RE_SSAA = re.compile(r"REGULARIZACI[OÓ]N\s+DE\s+SERVICIOS\s+DE\s+AJUSTE", re.I)
RE_SIGUIENTE = re.compile(r"REGULARIZACI[OÓ]N|IMPUESTO|FONDO DE EFICIENCIA|ALQUILER", re.I)
RE_CANTIDADES = re.compile(r"(" + NUM + r")\s*kWh\s+(" + NUM + r")\s+(" + NUM + r")\s*Eur", re.I)
RE_RANGO = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})")


def leer(texto):
    f = lector_generico(texto)
    f.avisos = []

    m = RE_NUMERO.search(texto)
    if m:
        f.numero = m.group(1)
    m = RE_EMISION.search(texto)
    if m:
        f.fecha_emision = fecha_es(m.group(1))
    m = RE_PERIODO.search(texto)
    if m:
        f.inicio, f.fin = fecha_es(m.group(1)), fecha_es(m.group(2))
    m = RE_TARIFA.search(texto)
    if m:
        f.tarifa = m.group(1).upper()

    energia = {}
    for m in RE_ENERGIA.finditer(texto):
        energia.setdefault(m.group(1), numero_es(m.group(2)))
    if energia:
        f.consumo_kwh = round(sum(energia.values()), 3)

    f.lineas_ssaa = []
    for m in RE_SSAA.finditer(texto):
        sig = RE_SIGUIENTE.search(texto, m.end())
        bloque = texto[m.end(): sig.start() if sig else m.end() + 400]
        l = LineaSSAA(concepto="Regularización de servicios de ajuste",
                      texto=" ".join((m.group(0) + bloque).split()))
        c = RE_CANTIDADES.search(bloque)
        if c:
            l.kwh, l.precio, l.importe = (numero_es(c.group(i)) for i in (1, 2, 3))
        r = RE_RANGO.search(bloque)
        if r:
            l.inicio, l.fin = fecha_es(r.group(1)), fecha_es(r.group(2))
            l.concepto += " %s–%s" % (l.inicio.strftime("%m/%Y"), l.fin.strftime("%m/%Y")) \
                if l.inicio.month != l.fin.month else " %s" % l.inicio.strftime("%m/%Y")
        if l.importe is None:
            f.avisos.append("Línea de SSAA sin cantidades legibles: %s" % l.texto[:120])
        f.lineas_ssaa.append(l)
    return comprobar_lineas(f)
