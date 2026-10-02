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
                        PERD_AGREGACIONES)

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


def _cabecera(ws, cab, ancho=14):
    ws.append(cab)
    for i in range(1, len(cab) + 1):
        ws.cell(1, i).font = NEGRITA
        ws.cell(1, i).fill = CABECERA
        ws.cell(1, i).alignment = Alignment(wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = ancho
    ws.freeze_panes = "A2"


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
    fila = _titulo(ws, fila, "Cláusula del contrato")
    fila = _tabla(ws, fila, descripcion_contrato(lineas[0][1].contrato))

    fila = _titulo(ws, fila, "Líneas de SSAA")
    cab = list(lineas[0][0].keys())
    for i, c in enumerate(cab, 1):
        ws.cell(fila, i, c).font = NEGRITA
        ws.cell(fila, i).fill = CABECERA
        ws.cell(fila, i).alignment = Alignment(wrap_text=True)
    fila += 1
    for resumen, r, _d in lineas:
        for i, c in enumerate(cab, 1):
            ws.cell(fila, i, resumen[c])
        if r.veredicto in COLORES:
            celda = ws.cell(fila, cab.index("Veredicto") + 1)
            celda.fill = PatternFill("solid", fgColor=COLORES[r.veredicto])
            celda.font = NEGRITA
        fila += 1
    tot_f = sum(r.facturado or 0 for _x, r, _d in lineas)
    tot_r = sum(r.importe for _x, r, _d in lineas)
    fila = _tabla(ws, fila + 1, [("Total facturado €", round(tot_f, 2)),
                                 ("Total recalculado €", round(tot_r, 2)),
                                 ("Diferencia € (facturado − recalculado)", round(tot_f - tot_r, 2))])

    for n, (resumen, r, _d) in enumerate(lineas, 1):
        fila = _titulo(ws, fila, "%d. %s" % (n, resumen["Concepto"]))
        filas = [("Índice medio aritmético €/MWh", round(r.indice_medio, 6))]
        if r.indice_ponderado is not None:
            filas.append(("Índice medio ponderado €/MWh", round(r.indice_ponderado, 6)))
        filas += [("Precio aplicado €/MWh (antes de pérdidas)", round(r.precio_aplicado, 6)),
                  ("Pérdidas aplicadas %", round(r.perd_aplicada, 4)),
                  ("Datos ESIOS", "; ".join("%s: %s" % kv for kv in r.liquidaciones.items()))]
        filas += [("Aviso", a) for a in r.avisos]
        fila = _tabla(ws, fila, filas)
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 26
    for col in "CDEFGHIJ":
        ws.column_dimensions[col].width = 16

    # detalle hora a hora de todas las lineas
    r0 = lineas[0][1]
    qh = any(r.resolucion == "qh" for _x, r, _d in lineas)
    horaria = r0.contrato.agregacion == "horaria"
    wd = wb.create_sheet("Detalle")
    cab = ["Línea", "Fecha", "Hora"] + (["Cuarto"] if qh else []) + \
          ["Consumo kWh", "Índice €/MWh", "Pérdidas %"] + \
          (["Precio aplicado €/MWh", "Importe €"] if horaria else [])
    _cabecera(wd, cab)
    for n, (_x, r, _d) in enumerate(lineas, 1):
        for k, e, v, p, precio, imp in r.detalle:
            fila_d = [n, k[0], k[1]] + ([k[2] if len(k) == 3 else None] if qh else []) + [e, v, p]
            if horaria:
                fila_d += [precio, imp]
            wd.append(fila_d)
    for celda in wd["B"][1:]:
        celda.number_format = "dd/mm/yyyy"

    diags = [(n, d) for n, (_x, _r, d) in enumerate(lineas, 1) if d]
    if diags:
        wg = wb.create_sheet("Diagnóstico")
        cab = ["Línea"] + list(diags[0][1][0].keys())
        _cabecera(wg, cab, 24)
        for n, diag in diags:
            for d in diag:
                wg.append([n] + [d[c] for c in cab[1:]])

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
