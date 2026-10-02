# -*- coding: utf-8 -*-
"""Informe Excel de una revision y fichas de contrato guardadas por CUPS."""

import datetime as dt
import io
import json
import os
import re

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

import config
from ssaa_motor import (Contrato, INDICES, AGREGACIONES, MECANISMOS, PERDIDAS,
                        PERD_AGREGACIONES, formula_clausula, pasos_calculo)

NEGRITA = Font(bold=True)
CABECERA = PatternFill("solid", fgColor="DDEBF7")
COLORES = {"CORRECTO": "C6EFCE", "FACTURADO DE MÁS": "FFC7CE", "FACTURADO DE MENOS": "FFEB9C"}


# ------------------------------------------------------------------ contratos
def cargar_contratos():
    if not config.FICHERO_CONTRATOS.exists():
        return {}
    with open(config.FICHERO_CONTRATOS, encoding="utf-8") as f:
        return {k: Contrato.desde_dict(v) for k, v in json.load(f).items()}


def guardar_contrato(contrato):
    if not contrato.cups:
        raise ValueError("El contrato necesita CUPS para guardarse")
    todos = {k: v.a_dict() for k, v in cargar_contratos().items()}
    todos[contrato.cups] = contrato.a_dict()
    tmp = str(config.FICHERO_CONTRATOS) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, config.FICHERO_CONTRATOS)


# -------------------------------------------------------------------- informe
def _tabla(ws, fila, filas):
    for i, (k, v) in enumerate(filas):
        ws.cell(fila + i, 1, k).font = NEGRITA
        ws.cell(fila + i, 2, v)
    return fila + len(filas) + 1


def _titulo(ws, fila, texto):
    c = ws.cell(fila, 1, texto)
    c.font = Font(bold=True, size=12)
    return fila + 1


def descripcion_contrato(c):
    filas = [("Comercializadora", c.comercializadora or "—"),
             ("Cláusula tipo", c.plantilla or "personalizada"),
             ("Descripción", c.descripcion or "—"),
             ("Tarifa", c.tarifa), ("Índice", INDICES[c.indice])]
    if c.indice == "componentes":
        filas.append(("Componentes", "; ".join(c.componentes)))
    filas += [("Agregación", AGREGACIONES[c.agregacion]),
              ("Mecanismo", MECANISMOS[c.mecanismo])]
    if c.mecanismo == "banda":
        filas += [("Ref. superior €/MWh", c.ref_superior),
                  ("Ref. inferior €/MWh", c.ref_inferior)]
    if c.mecanismo == "techo":
        filas.append(("Referencia de SSAA (techo) €/MWh", c.techo))
    if c.mecanismo in ("indexado_techo", "indexado_suelo_techo"):
        filas.append(("Precio máximo €/MWh", c.techo))
    if c.mecanismo == "indexado_suelo_techo":
        filas.append(("Precio mínimo €/MWh", c.suelo))
    if c.mecanismo == "fijo":
        filas.append(("Precio fijo €/MWh", c.precio_fijo))
    if c.mecanismo in ("indexado", "indexado_techo", "indexado_suelo_techo") and c.prima:
        filas.append(("Prima €/MWh", c.prima))
    filas.append(("Pérdidas", PERDIDAS[c.perdidas]))
    if c.perdidas == "fijo":
        filas.append(("Coef. pérdidas %", c.perd_fijo))
    elif c.perdidas != "ninguna" and c.agregacion != "horaria":
        filas.append(("Agregación pérdidas", PERD_AGREGACIONES[c.perd_agregacion]))
    filas.append(("Factor final", c.factor))
    return filas


def _cabecera(ws, cab, ancho=14, fila=1):
    for i, c in enumerate(cab, 1):
        celda = ws.cell(fila, i, c)
        celda.font = NEGRITA
        celda.fill = CABECERA
        celda.alignment = Alignment(wrap_text=True, vertical="top")
        if ancho:
            ws.column_dimensions[get_column_letter(i)].width = ancho


FMT = {"€": "#,##0.00", "€/MWh": "0.000000", "€/kWh": "0.000000000", "MWh": "0.000000",
       "%": "0.0000", "horas": "0", "cuartos": "0"}
NOMBRES_PARAM = {"techo": "Referencia de SSAA (techo) €/MWh",
                 "ref_superior": "Referencia superior €/MWh",
                 "ref_inferior": "Referencia inferior €/MWh",
                 "techo_max": "Precio máximo €/MWh", "suelo": "Precio mínimo €/MWh",
                 "prima": "Prima €/MWh", "precio_fijo": "Precio fijo €/MWh",
                 "perd_fijo": "Coeficiente de pérdidas fijo %", "factor": "Factor final",
                 "consumo": "Consumo real kWh", "facturado": "Importe facturado €",
                 "tolerancia": "Tolerancia para dar por correcta %"}


def _parametros(r):
    """[(clave, valor)] de los parametros que usan las formulas de esta linea."""
    c = r.contrato
    m = c.mecanismo
    out = []
    if m == "techo":
        out.append(("techo", c.techo))
    if m == "banda":
        out += [("ref_superior", c.ref_superior), ("ref_inferior", c.ref_inferior)]
    if m in ("indexado_techo", "indexado_suelo_techo"):
        out.append(("techo_max", c.techo))
    if m == "indexado_suelo_techo":
        out.append(("suelo", c.suelo))
    if m in ("indexado", "indexado_techo", "indexado_suelo_techo"):
        out.append(("prima", c.prima))
    if m == "fijo":
        out.append(("precio_fijo", c.precio_fijo))
    if c.perdidas == "fijo":
        out.append(("perd_fijo", c.perd_fijo))
    out.append(("factor", c.factor))
    if c.agregacion != "horaria":
        out.append(("consumo", r.energia_mwh * 1000))
    if r.facturado is not None:
        out += [("facturado", r.facturado), ("tolerancia", r.tolerancia_pct)]
    return out


def _mecanismo_excel(c, x, P):
    """Formula Excel del mecanismo sobre la celda x; P = {parametro: celda}."""
    m = c.mecanismo
    if m == "techo":
        return "MAX(%s-%s,0)" % (x, P["techo"])
    if m == "banda":
        return "IF(%s>%s,%s-%s,IF(%s<%s,-(%s-%s),0))" % (
            x, P["ref_superior"], x, P["ref_superior"], x, P["ref_inferior"],
            P["ref_inferior"], x)
    if m == "indexado":
        return "%s+%s" % (x, P["prima"])
    if m == "indexado_techo":
        return "MIN(%s,%s)+%s" % (x, P["techo_max"], P["prima"])
    if m == "indexado_suelo_techo":
        return "MAX(%s,MIN(%s,%s))+%s" % (P["suelo"], x, P["techo_max"], P["prima"])
    return P["precio_fijo"]


def _hoja_detalle(wb, n, r, P):
    """Detalle hora a hora (o cuarto a cuarto) de una linea. Devuelve sus rangos."""
    c = r.contrato
    wd = wb.create_sheet("Detalle %d" % n)
    qh = r.resolucion == "qh"
    horaria = c.agregacion == "horaria"
    cab = ["Fecha", "Hora"] + (["Cuarto"] if qh else []) + \
          ["Consumo kWh (Eh)", "SSAA €/MWh (SSAAh)", "Pérdidas % (PERDh)"] + \
          (["Precio P(SSAAh) €/MWh", "Importe € = Eh/1000 × P × (1+PERDh/100) × Factor"]
           if horaria else [])
    _cabecera(wd, cab)
    base = 3 if qh else 2
    L = {k: get_column_letter(base + i + 1) for i, k in enumerate(("e", "x", "p", "pr", "imp"))}
    for i, (k, e, v, p, _precio, _imp) in enumerate(r.detalle, 2):
        wd.cell(i, 1, k[0]).number_format = "dd/mm/yyyy"
        wd.cell(i, 2, k[1])
        if qh:
            wd.cell(i, 3, k[2] if len(k) == 3 else None)
        wd.cell(i, base + 1, e)
        wd.cell(i, base + 2, v).number_format = "0.0000"
        wd.cell(i, base + 3, p).number_format = "0.000"
        if horaria:
            x = "%s%d" % (L["x"], i)
            wd.cell(i, base + 4, "=" + _mecanismo_excel(c, x, P)).number_format = "0.000000"
            wd.cell(i, base + 5, "=%s%d/1000*%s%d*(1+%s%d/100)*%s" % (
                L["e"], i, L["pr"], i, L["p"], i, P["factor"])).number_format = "0.0000"
    ultima = len(r.detalle) + 1
    wd.freeze_panes = "A2"
    wd.column_dimensions[L["imp"]].width = 22
    hoja = "'Detalle %d'" % n
    return {k: "%s!%s2:%s%d" % (hoja, col, col, ultima) for k, col in L.items()}


def _hoja_calculo(wb, n, resumen, r):
    c = r.contrato
    ws = wb.create_sheet("Cálculo %d" % n)
    hoja = "'Cálculo %d'" % n
    fila = _titulo(ws, 1, "Cálculo de la línea %d — %s" % (n, resumen["Concepto"]))
    ws.cell(fila, 1, "Periodo: %s" % resumen["Periodo"])
    fila += 2

    fila = _titulo(ws, fila, "Fórmulas de la cláusula")
    for linea in formula_clausula(c):
        ws.cell(fila, 1, linea)
        fila += 1
    fila += 1

    fila = _titulo(ws, fila, "Parámetros")
    P = {}
    for clave, valor in _parametros(r):
        ws.cell(fila, 1, NOMBRES_PARAM[clave]).font = NEGRITA
        ws.cell(fila, 2, valor)
        P[clave] = "%s!$B$%d" % (hoja, fila)
        fila += 1
    fila += 1

    rangos = _hoja_detalle(wb, n, r, P)
    fila = _titulo(ws, fila, "Cálculo paso a paso")
    ws.cell(fila, 1, "La columna «Resultado» es una fórmula de Excel sobre la hoja «Detalle %d» y "
                     "los parámetros; «Valor del programa» es lo que calculó la aplicación." % n)
    fila += 1
    _cabecera(ws, ["Paso", "Concepto", "Fórmula", "Sustitución", "Resultado (fórmula Excel)",
                   "Valor del programa", "Unidad"], ancho=None, fila=fila)
    fila += 1
    pasos = pasos_calculo(r)
    filas = {p["clave"]: fila + i for i, p in enumerate(pasos)}
    E = {k: "E%d" % v for k, v in filas.items()}
    horaria = c.agregacion == "horaria"
    pond = c.agregacion == "media_ponderada"

    def formula(clave):
        if clave == "n":
            return "=COUNT(%s)" % rangos["x"]
        if clave == "ssaa":
            if horaria or pond:
                return "=SUMPRODUCT(%s,%s)/SUM(%s)" % (rangos["e"], rangos["x"], rangos["e"])
            return "=AVERAGE(%s)" % rangos["x"]
        if clave == "perd":
            if c.perdidas == "fijo":
                return "=" + P["perd_fijo"]
            if c.perdidas == "ninguna":
                return "=0"
            if c.perd_agregacion == "media_ponderada":
                return "=SUMPRODUCT(%s,%s)/SUM(%s)" % (rangos["e"], rangos["p"], rangos["e"])
            return "=AVERAGE(%s)" % rangos["p"]
        if clave == "precio":
            return "=" + _mecanismo_excel(c, E["ssaa"], P)
        if clave == "precio_final":
            return "=%s*(1+%s/100)*%s" % (E["precio"], E["perd"], P["factor"])
        if clave == "precio_kwh":
            return "=%s/1000" % E["precio_final"]
        if clave == "mwh":
            return "=SUM(%s)/1000" % rangos["e"] if horaria else "=%s/1000" % P["consumo"]
        if clave == "importe":
            return "=SUM(%s)" % rangos["imp"] if horaria else "=%s*%s" % (E["mwh"], E["precio_final"])
        if clave == "precio_ef":
            return "=IF(%s=0,0,%s/%s)" % (E["mwh"], E["importe"], E["mwh"])
        if clave == "facturado":
            return "=" + P["facturado"]
        if clave == "dif":
            return "=%s-%s" % (E["facturado"], E["importe"])
        if clave == "dif_pct":
            return '=IF(%s=0,"",%s/ABS(%s)*100)' % (E["importe"], E["dif"], E["importe"])
        if clave == "veredicto":
            d, i = E["dif"], E["importe"]
            return ('=IF(ABS({d})<0.01,"CORRECTO",IF(AND({i}<>0,ABS({d})<=ABS({i})*{t}/100),'
                    '"CORRECTO",IF({d}>0,"FACTURADO DE MÁS","FACTURADO DE MENOS")))').format(
                d=d, i=i, t=P["tolerancia"])
        return None

    for p in pasos:
        f = filas[p["clave"]]
        ws.cell(f, 1, p["paso"])
        ws.cell(f, 2, p["concepto"]).font = NEGRITA
        ws.cell(f, 3, p["formula"])
        ws.cell(f, 4, p["sustitucion"])
        fx = formula(p["clave"])
        ws.cell(f, 5, fx if fx else p["valor"])
        ws.cell(f, 6, p["valor"])
        ws.cell(f, 7, p["unidad"])
        for col in (5, 6):
            ws.cell(f, col).number_format = FMT.get(p["unidad"], "General")
        for col in (3, 4):
            ws.cell(f, col).alignment = Alignment(wrap_text=True, vertical="top")
    if "veredicto" in filas and r.veredicto in COLORES:
        for col in (5, 6):
            ws.cell(filas["veredicto"], col).fill = PatternFill("solid", fgColor=COLORES[r.veredicto])
            ws.cell(filas["veredicto"], col).font = NEGRITA
    fila += len(pasos) + 1

    fila = _titulo(ws, fila, "Datos de ESIOS usados")
    for k, v in r.liquidaciones.items():
        ws.cell(fila, 1, k)
        ws.cell(fila, 2, v)
        fila += 1
    if r.avisos:
        fila = _titulo(ws, fila + 1, "Avisos")
        for a_ in r.avisos:
            ws.cell(fila, 1, a_)
            fila += 1
    for col, ancho in zip("ABCDEFG", (34, 38, 52, 44, 20, 20, 9)):
        ws.column_dimensions[col].width = ancho


def generar_excel(lineas, factura):
    """Excel de la revision en bytes.

    lineas: [(resumen dict, Resultado, diagnostico)], una por linea de SSAA.
    factura: dict de campos de cabecera a mostrar.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    fila = _titulo(ws, 1, "Revisión de SSAA — %s" % dt.date.today().strftime("%d/%m/%Y"))
    fila = _titulo(ws, fila + 1, "Factura")
    fila = _tabla(ws, fila, list(factura.items()))
    c0 = lineas[0][1].contrato
    fila = _titulo(ws, fila, "Cláusula del contrato")
    fila = _tabla(ws, fila, descripcion_contrato(c0))
    fila = _titulo(ws, fila, "Fórmulas aplicadas")
    for linea in formula_clausula(c0):
        ws.cell(fila, 1, linea)
        fila += 1
    fila += 1

    fila = _titulo(ws, fila, "Líneas de SSAA")
    cab = list(lineas[0][0].keys()) + ["Cálculo"]
    _cabecera(ws, cab, ancho=None, fila=fila)
    fila += 1
    for n, (resumen, r, _d) in enumerate(lineas, 1):
        for i, k in enumerate(cab[:-1], 1):
            ws.cell(fila, i, resumen[k])
        ws.cell(fila, len(cab), "Hojas «Cálculo %d» y «Detalle %d»" % (n, n))
        if r.veredicto in COLORES:
            celda = ws.cell(fila, cab.index("Veredicto") + 1)
            celda.fill = PatternFill("solid", fgColor=COLORES[r.veredicto])
            celda.font = NEGRITA
        fila += 1
    tot_f = sum(r.facturado or 0 for _x, r, _d in lineas)
    tot_r = sum(r.importe for _x, r, _d in lineas)
    _tabla(ws, fila + 1, [("Total facturado €", round(tot_f, 2)),
                          ("Total recalculado €", round(tot_r, 2)),
                          ("Diferencia € (facturado − recalculado)", round(tot_f - tot_r, 2))])
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 26
    for col in "CDEFGHIJK":
        ws.column_dimensions[col].width = 16

    for n, (resumen, r, _d) in enumerate(lineas, 1):
        _hoja_calculo(wb, n, resumen, r)

    diags = [(n, d) for n, (_x, _r, d) in enumerate(lineas, 1) if d]
    if diags:
        wg = wb.create_sheet("Diagnóstico")
        wg.cell(1, 1, "Variantes de cálculo más cercanas a lo facturado (para ver cómo ha "
                      "calculado la comercializadora)").font = NEGRITA
        cab = ["Línea"] + list(diags[0][1][0].keys())
        _cabecera(wg, cab, 24, fila=2)
        for n, diag in diags:
            for d in diag:
                wg.append([n] + [d[k] for k in cab[1:]])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def guardar_informe(datos, r, cups, numero):
    config.CARPETA_REVISIONES.mkdir(exist_ok=True)
    limpio = lambda s: re.sub(r"[^A-Za-z0-9_-]", "", s or "") or "sin"
    nombre = "%s_%s_%s.xlsx" % (r.inicio.strftime("%Y-%m"), limpio(cups), limpio(numero))
    ruta = config.CARPETA_REVISIONES / nombre
    ruta.write_bytes(datos)
    return ruta
