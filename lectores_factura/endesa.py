# -*- coding: utf-8 -*-
"""
Endesa Energia (grandes cuentas).

Maqueta observada:
  Factura nº: XXXXXXXXXXXXXXX           Fecha Factura: 1 de enero de 2026
  Periodo facturación: dd/mm/aaaa al dd/mm/aaaa
  CUPS: ES00...                         Modalidad de Contrato: 6.xTD
  Término de Energía Variable
      P3: 1.000,000 kWh x 0,050000 Eur/kWh = 50,00 Eur
  Regularización Servicios Ajuste (SSAA)   1.000,000000 kWh x 0,002000 euros/kWh   2,00
"""

import re

from .base import (LineaSSAA, RE_FECHA, RE_FECHA_LETRA, RE_RANGO, comprobar_lineas,
                   fecha_es, lector_generico, numero_es)

NUM = r"-?\d[\d.]*(?:,\d+)?"

RE_NUMERO = re.compile(r"Factura\s+n[ºo°]\s*:?\s*([A-Z0-9]{8,})", re.I)
RE_EMISION = re.compile(r"Fecha\s+Factura\s*:\s*(?:" + RE_FECHA_LETRA + "|" + RE_FECHA + ")", re.I)
RE_PERIODO = re.compile(r"Periodo\s+facturaci[oó]n\s*:\s*(?:del\s+)?" + RE_FECHA +
                        r"\s+al\s+" + RE_FECHA, re.I)
RE_TARIFA = re.compile(r"Modalidad\s+de\s+(?:Contrato|la\s+tarifa\s+de\s+acceso)\s*:\s*"
                       r"([236]\.[0-4]TD(?:VE)?)", re.I)
RE_ENERGIA = re.compile(r"\bP([1-6])\s*:\s*(" + NUM + r")\s*kWh\s*x\s*" + NUM + r"\s*Eur/kWh", re.I)
RE_SSAA = re.compile(
    r"(Regularizaci[oó]n\s+(?:de\s+)?Servicios?\s+(?:de\s+)?Ajuste[^\n]*?)\s+"
    r"(" + NUM + r")\s*kWh\s*x\s*(" + NUM + r")\s*(?:euros|eur|€)\s*/\s*kWh\s+(" + NUM + r")",
    re.I)


def leer(texto):
    f = lector_generico(texto)
    f.avisos = []

    m = RE_NUMERO.search(texto)
    if m:
        f.numero = m.group(1)
    m = RE_EMISION.search(texto)
    if m:
        f.fecha_emision = fecha_es(m.group(1) or m.group(2))
    m = RE_PERIODO.search(texto)
    if m:
        f.inicio, f.fin = fecha_es(m.group(1)), fecha_es(m.group(2))
    m = RE_TARIFA.search(texto)
    if m:
        f.tarifa = m.group(1).upper()

    # energia activa del periodo: suma de las lineas "Pn: X kWh x precio Eur/kWh"
    energia = {}
    for m in RE_ENERGIA.finditer(texto):
        energia.setdefault(m.group(1), numero_es(m.group(2)))
    if energia:
        f.consumo_kwh = round(sum(energia.values()), 3)

    f.lineas_ssaa = []
    for m in RE_SSAA.finditer(texto):
        l = LineaSSAA(concepto=" ".join(m.group(1).split()), kwh=numero_es(m.group(2)),
                      precio=numero_es(m.group(3)), importe=numero_es(m.group(4)),
                      texto=" ".join(m.group(0).split()))
        r = RE_RANGO.search(m.group(1))
        if r:
            l.inicio, l.fin = fecha_es(r.group(1)), fecha_es(r.group(2))
        f.lineas_ssaa.append(l)

    if f.consumo_kwh and len(f.lineas_ssaa) == 1 and f.lineas_ssaa[0].kwh and \
            abs(f.lineas_ssaa[0].kwh - f.consumo_kwh) > 1:
        f.avisos.append("Los kWh de la línea de SSAA (%s) no coinciden con la energía "
                        "facturada (%s)." % (f.lineas_ssaa[0].kwh, f.consumo_kwh))
    return comprobar_lineas(f)
