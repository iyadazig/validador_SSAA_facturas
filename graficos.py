# -*- coding: utf-8 -*-
"""
Graficos de la revision (Altair), con fechas en espanol, colores corporativos y
las referencias del contrato.

  grafico_ssaa(r)     serie horaria (o cuartohoraria) del indice de SSAA, la media
                      que entra en la formula (SSAA reales) y las referencias
  grafico_consumo(r)  consumo de cada hora (o cuarto) de la curva
"""

import datetime as dt

import altair as alt
import pandas as pd

import estilo

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
# etiquetas del eje X: "3 ago" (Vega cuenta los meses desde 0)
EJE_FECHA = alt.Axis(title=None, grid=False, labelColor=estilo.GRIS, tickColor=estilo.BEIS_BORDE,
                     domainColor=estilo.BEIS_BORDE,
                     labelExpr="date(datum.value) + ' ' + %s[month(datum.value)]" % MESES)

NOMBRE_SERIE = {"sah_pvpc": "Total SAH",
                "pfm_ssaa": "SSAA PFMHORAS_COM",
                "componentes": "SSAA componentes OS",
                "ssaa_esios": "Total SSAA ESIOS",
                "fijo": "Precio fijo"}


def _num(v, d=2):
    return ("%.*f" % (d, v)).replace(".", ",")


def _momento(k):
    """Clave ESIOS -> instante de inicio (los dias de 25 h siguen siendo crecientes)."""
    minutos = (k[1] - 1) * 60 + ((k[2] - 1) * 15 if len(k) == 3 else 0)
    return dt.datetime.combine(k[0], dt.time()) + dt.timedelta(minutes=minutos)


def _etiqueta_hora(k):
    m = _momento(k)
    return "%s %s" % (m.strftime("%d/%m/%Y"), m.strftime("%H:%M"))


def lineas_referencia(r):
    """[(nombre en la leyenda, valor, tipo)] de la media y las referencias del contrato.
    tipo: media | ref_sup | ref_inf"""
    c = r.contrato
    pond = c.agregacion == "media_ponderada" or c.agregacion == "horaria"
    media = r.indice_aplicado if pond and r.indice_ponderado is not None else r.indice_medio
    out = [("SSAA reales (media %s): %s €/MWh" % ("ponderada" if pond and r.indice_ponderado
                                                   is not None else "aritmética", _num(media)),
            media, "media")]
    m = c.mecanismo
    if m == "banda":
        out.append(("Referencia superior: %s €/MWh" % _num(c.ref_superior, 3), c.ref_superior,
                    "ref_sup"))
        out.append(("Referencia inferior: %s €/MWh" % _num(c.ref_inferior, 3), c.ref_inferior,
                    "ref_inf"))
    elif m == "techo":
        out.append(("Referencia de SSAA (techo): %s €/MWh" % _num(c.techo, 3), c.techo, "ref_sup"))
    elif m in ("indexado_techo", "indexado_suelo_techo"):
        out.append(("Precio máximo: %s €/MWh" % _num(c.techo, 3), c.techo, "ref_sup"))
        if m == "indexado_suelo_techo":
            out.append(("Precio mínimo: %s €/MWh" % _num(c.suelo, 3), c.suelo, "ref_inf"))
    return out


def grafico_ssaa(r, alto=320):
    c = r.contrato
    unidad = "cuartohorario" if r.resolucion == "qh" else "horario"
    nombre = "%s %s (€/MWh)" % (NOMBRE_SERIE.get(c.indice, "SSAA"), unidad)
    serie = pd.DataFrame([{"Momento": _momento(k), "Valor": v, "Serie": nombre,
                           "Fecha y hora": _etiqueta_hora(k), "Texto": "%s €/MWh" % _num(v)}
                          for k, _e, v, _p, _pr, _i in r.detalle])
    refs = lineas_referencia(r)
    lineas = pd.DataFrame([{"Valor": v, "Serie": n, "Texto": "%s €/MWh" % _num(v, 3)}
                           for n, v, _t in refs])

    estilos = {"media": (estilo.NEGRO, [1, 0]),
               "ref_sup": (estilo.GRIS, [7, 4]),
               "ref_inf": (estilo.GRIS_CLARO, [3, 3])}
    dominio = [nombre] + [n for n, _v, _t in refs]
    colores = [estilo.GRANATE] + [estilos[t][0] for _n, _v, t in refs]
    trazos = [[1, 0]] + [estilos[t][1] for _n, _v, t in refs]
    leyenda = alt.Legend(title=None, orient="bottom", direction="vertical", labelLimit=440,
                         labelColor=estilo.NEGRO, labelFontSize=12, symbolType="stroke",
                         symbolSize=500, symbolStrokeWidth=2.4)
    color = alt.Color("Serie:N", scale=alt.Scale(domain=dominio, range=colores), legend=leyenda)
    # misma leyenda que el color: Vega las une y muestra cada linea con su trazo
    trazo = alt.StrokeDash("Serie:N", scale=alt.Scale(domain=dominio, range=trazos), legend=leyenda)

    valores = list(serie["Valor"]) + list(lineas["Valor"])
    margen = (max(valores) - min(valores)) * 0.05 or 1
    eje_y = alt.Y("Valor:Q", title="€/MWh",
                  scale=alt.Scale(domain=[min(valores) - margen, max(valores) + margen]),
                  axis=alt.Axis(labelColor=estilo.GRIS, gridColor="#EFE9E4",
                                titleColor=estilo.GRIS, format=".0f"))

    curva = alt.Chart(serie).mark_line(strokeWidth=1.3).encode(
        x=alt.X("Momento:T", axis=EJE_FECHA), y=eje_y, color=color, strokeDash=trazo)
    # etiqueta del punto mas cercano al cursor, con guia vertical
    cerca = alt.selection_point(nearest=True, on="pointerover", fields=["Momento"], empty=False,
                                clear="pointerout")
    etiqueta = [alt.Tooltip("Fecha y hora:N"), alt.Tooltip("Texto:N", title="SSAA")]
    detector = alt.Chart(serie).mark_rule(opacity=0, strokeWidth=8).encode(
        x="Momento:T", tooltip=etiqueta).add_params(cerca)
    guia = alt.Chart(serie).mark_rule(color=estilo.GRIS_CLARO, strokeWidth=1).encode(
        x="Momento:T").transform_filter(cerca)
    puntos = alt.Chart(serie).mark_point(filled=True, size=70, color=estilo.GRANATE).encode(
        x="Momento:T", y="Valor:Q", tooltip=etiqueta).transform_filter(cerca)
    # grosor fijo: una codificacion de tamano se mezclaria con la leyenda y la encogeria
    reglas = alt.Chart(lineas).mark_rule(strokeWidth=2).encode(
        y="Valor:Q", color=color, strokeDash=trazo,
        tooltip=[alt.Tooltip("Serie:N", title="Línea"), alt.Tooltip("Texto:N", title="Valor")])
    return (curva + reglas + detector + guia + puntos).properties(height=alto).configure(
        font="Arial").configure_view(stroke=None)


def grafico_consumo(r, alto=170):
    if not any(e for _k, e, *_ in r.detalle):
        return None
    unidad = "cuarto de hora" if r.resolucion == "qh" else "hora"
    datos = pd.DataFrame([{"Momento": _momento(k), "Consumo": e or 0.0,
                           "Fecha y hora": _etiqueta_hora(k), "Texto": "%s kWh" % _num(e or 0, 1),
                           "Serie": "Consumo por %s (kWh)" % unidad}
                          for k, e, _v, _p, _pr, _i in r.detalle])
    return alt.Chart(datos).mark_bar(color=estilo.GRIS_CLARO).encode(
        x=alt.X("Momento:T", axis=EJE_FECHA),
        y=alt.Y("Consumo:Q", title="kWh", axis=alt.Axis(labelColor=estilo.GRIS,
                                                       gridColor="#EFE9E4", format=".0f")),
        color=alt.Color("Serie:N", scale=alt.Scale(range=[estilo.GRIS_CLARO]),
                        legend=alt.Legend(title=None, orient="bottom", labelFontSize=12)),
        tooltip=[alt.Tooltip("Fecha y hora:N"), alt.Tooltip("Texto:N", title="Consumo")]
    ).properties(height=alto).configure(font="Arial").configure_view(stroke=None)
