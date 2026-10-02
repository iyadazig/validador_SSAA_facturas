# -*- coding: utf-8 -*-
"""
REVISOR DE SSAA EN FACTURAS — app local
=======================================
    streamlit run app_revision_ssaa.py

Abre http://localhost:8501. Todo se ejecuta en este PC: ni la factura ni la
curva salen de el. Los datos de ESIOS se leen de los Excel historicos de
config.CARPETA_ESIOS (proyecto Descarga_datos_ESIOS).
"""

import datetime as dt
import hashlib

import pandas as pd
import streamlit as st

import config
import curva_consumo
import informe
import ssaa_datos_esios as esios
import ssaa_motor as motor
from lectores_factura import leer_factura

st.set_page_config(page_title="Revisor SSAA", page_icon="⚡", layout="wide")
ss = st.session_state


def opciones(dic, clave):
    """selectbox sobre un dict {codigo: etiqueta}."""
    codigos = list(dic)
    return st.selectbox(clave[1], codigos, format_func=dic.get, key=clave[0])


def fijar(prefijo, valores):
    for k, v in valores.items():
        ss[prefijo + k] = v


# ================================================================ barra lateral
with st.sidebar:
    st.header("Configuración")
    st.caption("Datos ESIOS en:")
    st.code(str(config.CARPETA_ESIOS), language=None)
    if not config.CARPETA_ESIOS.exists():
        st.error("No existe la carpeta de datos de ESIOS.")
    tolerancia = st.number_input("Tolerancia para dar por correcta (%)", 0.0, 10.0,
                                 config.TOLERANCIA_PCT, 0.1)
    st.caption("Se compara siempre con el último dato publicado que haya en los Excel. "
               "Si falta un periodo, actualízalo con los scripts de Descarga_datos_ESIOS:")
    st.code("python descarga_PVPC_diario_excel.py AAAA-MM-DD AAAA-MM-DD\n"
            "python descarga_componentes_precio_excel.py", language="bat")

st.title("Revisión de servicios de ajuste (SSAA) en facturas")

# valores iniciales de los campos (los widgets no llevan value= para no chocar
# con los que se rellenan al leer el PDF o al cargar una ficha)
for k, v in {"f_comercializadora": "", "f_numero": "", "f_emision": None, "f_cups": "",
             "f_tarifa": "6.1TD", "f_inicio": None, "f_fin": None, "f_consumo": None,
             "f_importe": None}.items():
    ss.setdefault(k, v)
if "c_tarifa" not in ss:
    fijar("c_", motor.Contrato().a_dict())

# ===================================================================== factura
st.header("1. Factura")
pdf = st.file_uploader("Factura en PDF (opcional: también se puede rellenar a mano)",
                       type=["pdf"])
if pdf is not None:
    datos_pdf = pdf.getvalue()
    huella = hashlib.md5(datos_pdf).hexdigest()
    if ss.get("pdf_huella") != huella:
        try:
            f = leer_factura(datos_pdf)
        except Exception as e:      # PDF corrupto o protegido
            st.error("No se ha podido leer el PDF: %s" % e)
        else:
            ss.pdf_huella = huella
            ss.factura_leida = f
            fijar("f_", {"comercializadora": f.comercializadora, "numero": f.numero,
                         "emision": f.fecha_emision, "cups": f.cups,
                         "tarifa": f.tarifa if f.tarifa in motor.TARIFAS else "6.1TD",
                         "inicio": f.inicio, "fin": f.fin, "consumo": f.consumo_kwh,
                         "importe": f.importe_ssaa})

leida = ss.get("factura_leida")
if leida is not None and pdf is not None:
    st.caption("Lector usado: **%s**. Revisa y corrige los datos antes de calcular." % leida.lector)
    for a in leida.avisos:
        st.warning(a)
    with st.expander("Líneas de SSAA encontradas en el PDF (%d)" % len(leida.lineas_ssaa)):
        for l in leida.lineas_ssaa:
            st.write("`%s` → números: %s" % (l.texto, l.numeros))
    with st.expander("Valores en kWh encontrados"):
        for v, t in leida.candidatos_kwh[:40]:
            st.write("%s kWh — `%s`" % (v, t))
    with st.expander("Texto completo del PDF"):
        st.text(leida.texto)

c1, c2, c3 = st.columns(3)
with c1:
    st.text_input("Comercializadora", key="f_comercializadora")
    st.text_input("Nº de factura", key="f_numero")
    st.date_input("Fecha de emisión", key="f_emision", format="DD/MM/YYYY")
with c2:
    cups = st.text_input("CUPS", key="f_cups").strip().upper()
    st.date_input("Inicio del periodo", key="f_inicio", format="DD/MM/YYYY")
    st.date_input("Fin del periodo (incluido)", key="f_fin", format="DD/MM/YYYY")
with c3:
    st.selectbox("Tarifa de acceso", motor.TARIFAS, key="f_tarifa")
    st.number_input("Consumo del periodo (kWh)", min_value=0.0, format="%.3f",
                    key="f_consumo")
    st.number_input("Importe de SSAA facturado (€) — negativo si es abono",
                    format="%.2f", key="f_importe")

# ==================================================================== contrato
st.header("2. Condiciones de SSAA del contrato")
guardados = informe.cargar_contratos()
if cups and ss.get("contrato_cups") != cups:
    ss.contrato_cups = cups
    if cups in guardados:
        fijar("c_", guardados[cups].a_dict())
        st.success("Cargada la ficha guardada de este CUPS.")
    else:
        # ficha nueva: tarifa de la factura
        ss.c_tarifa = ss.get("f_tarifa", "6.1TD")
if cups and cups not in guardados:
    st.info("No hay ficha guardada para este CUPS: rellénala y pulsa «Guardar ficha».")

k1, k2, k3 = st.columns(3)
with k1:
    st.text_input("Descripción del contrato", key="c_descripcion")
    opciones(motor.MECANISMOS, ("c_mecanismo", "Mecanismo"))
    opciones(motor.INDICES, ("c_indice", "Índice ESIOS"))
    if ss.c_indice == "componentes":
        try:
            cols = esios.columnas_componentes()
        except Exception as e:
            cols = []
            st.error("No se pueden leer las columnas de componentes: %s" % e)
        ss.c_componentes = [c for c in ss.get("c_componentes", []) if c in cols]
        st.multiselect("Componentes que suman", cols, key="c_componentes")
    opciones(motor.AGREGACIONES, ("c_agregacion", "Cómo se agrega el índice"))
with k2:
    mec = ss.c_mecanismo
    if mec == "banda":
        st.number_input("Referencia superior €/MWh", format="%.3f", key="c_ref_superior")
        st.number_input("Referencia inferior €/MWh", format="%.3f", key="c_ref_inferior")
    if mec in ("techo", "suelo_techo"):
        st.number_input("Techo €/MWh", format="%.3f", key="c_techo")
    if mec == "suelo_techo":
        st.number_input("Suelo €/MWh", format="%.3f", key="c_suelo")
    if mec == "fijo":
        st.number_input("Precio fijo €/MWh", format="%.3f", key="c_precio_fijo")
    if mec in ("indexado", "techo", "suelo_techo"):
        st.number_input("Prima / fee €/MWh", format="%.3f", key="c_prima")
    st.number_input("Factor final (1,015 = impuesto municipal)", format="%.4f",
                    step=0.001, key="c_factor")
with k3:
    opciones(motor.PERDIDAS, ("c_perdidas", "Pérdidas"))
    if ss.c_perdidas == "fijo":
        st.number_input("Coeficiente de pérdidas %", format="%.3f", key="c_perd_fijo")
    elif ss.c_perdidas != "ninguna" and ss.c_agregacion != "horaria":
        opciones(motor.PERD_AGREGACIONES, ("c_perd_agregacion", "Cómo se agregan las pérdidas"))
    st.selectbox("Tarifa para las pérdidas", motor.TARIFAS, key="c_tarifa")
    st.selectbox("Zona", ["Península", "Baleares", "Canarias"], key="c_zona")


def contrato_actual():
    d = {k[2:]: v for k, v in ss.items() if k.startswith("c_")}
    d["cups"] = cups
    return motor.Contrato.desde_dict(d)


if st.button("Guardar ficha de contrato", disabled=not cups):
    informe.guardar_contrato(contrato_actual())
    st.success("Ficha guardada para %s en %s" % (cups, config.FICHERO_CONTRATOS.name))

if ss.c_mecanismo == "banda":
    st.caption("Banda: cargo = consumo × (SSAA − ref. sup.) × (1+perd) × factor si supera la "
               "referencia superior; abono = consumo × (ref. inf. − SSAA) × (1+perd) × factor "
               "si queda por debajo. El abono se calcula con signo negativo.")

# ======================================================================= curva
st.header("3. Curva de consumo")
necesita = ss.c_agregacion in ("media_ponderada", "horaria") or \
    (ss.c_perdidas not in ("ninguna", "fijo") and ss.get("c_perd_agregacion") == "media_ponderada")
st.caption("Esta cláusula **necesita** la curva." if necesita else
           "Esta cláusula solo usa el consumo total: la curva es opcional "
           "(sirve para comprobar el consumo y para el diagnóstico).")
origen = st.radio("Origen", ["Subir fichero", "Gemweb (API)", "Sin curva"], horizontal=True)
curva = None
if origen == "Subir fichero":
    fc = st.file_uploader("Curva horaria o cuartohoraria (CSV, XLSX o XLS)",
                          type=["csv", "txt", "xlsx", "xls"])
    if fc is not None:
        try:
            curva = curva_consumo.leer_curva(fc.getvalue(), fc.name)
        except curva_consumo.ErrorCurva as e:
            st.error(str(e))
        if curva is not None:
            st.write("Leída: **%s**, %d registros, %s a %s, total **%.1f kWh**. Columnas: %s"
                     % ("cuartohoraria" if curva.resolucion == "qh" else "horaria",
                        len(curva.valores), curva.inicio, curva.fin, curva.total_kwh,
                        curva.columnas))
            for a in curva.avisos[:10]:
                st.warning(a)
            if len(curva.avisos) > 10:
                st.warning("… y %d avisos más." % (len(curva.avisos) - 10))
elif origen == "Gemweb (API)":
    st.info("Integración con Gemweb pendiente de la documentación de su API. "
            "Mientras tanto, exporta la curva desde Gemweb y súbela como fichero.")

# =================================================================== resultado
st.header("4. Resultado")
ini, fin = ss.get("f_inicio"), ss.get("f_fin")
if curva is not None and (ini is None or fin is None):
    st.caption("Sin fechas de factura se usa el periodo de la curva.")
    ini, fin = ini or curva.inicio, fin or curva.fin

if st.button("Revisar SSAA", type="primary", disabled=ini is None or fin is None):
    contrato = contrato_actual()
    consumo = ss.get("f_consumo")
    facturado = ss.get("f_importe")
    try:
        with st.spinner("Leyendo ESIOS y calculando…"):
            r = motor.revisar(contrato, ini, fin, consumo, facturado, curva, tolerancia)
            diag = motor.diagnostico(contrato, ini, fin, consumo, facturado, curva)
    except motor.ErrorRevision as e:
        st.error(str(e))
    else:
        ss.resultado = (r, diag)

if ss.get("resultado"):
    r, diag = ss.resultado
    colores = {"CORRECTO": "green", "FACTURADO DE MÁS": "red", "FACTURADO DE MENOS": "orange"}
    st.subheader(":%s[%s]" % (colores.get(r.veredicto, "gray"), r.veredicto))
    m = st.columns(4)
    m[0].metric("Recalculado", "%.2f €" % r.importe)
    m[1].metric("Facturado", "%.2f €" % r.facturado if r.facturado is not None else "—")
    m[2].metric("Diferencia", "%+.2f €" % r.diferencia if r.diferencia is not None else "—",
                "%+.2f %%" % r.diferencia_pct if r.diferencia_pct is not None else None,
                delta_color="inverse")
    m[3].metric("Energía", "%.3f MWh" % r.energia_mwh)
    m = st.columns(4)
    m[0].metric("Índice medio aritmético", "%.6f €/MWh" % r.indice_medio)
    m[1].metric("Índice ponderado", "%.6f €/MWh" % r.indice_ponderado
                if r.indice_ponderado is not None else "—")
    m[2].metric("Precio aplicado", "%.6f €/MWh" % r.precio_aplicado)
    m[3].metric("Pérdidas aplicadas", "%.4f %%" % r.perd_aplicada)
    for a in r.avisos:
        st.warning(a)
    st.caption("Datos ESIOS: " + "; ".join("%s: %s" % kv for kv in r.liquidaciones.items()))

    filas = [{"Momento": dt.datetime.combine(k[0], dt.time()) +
              dt.timedelta(minutes=(k[1] - 1) * 60 + ((k[2] - 1) * 15 if len(k) == 3 else 0)),
              "Índice €/MWh": v, "Consumo kWh": e}
             for k, e, v, _p, _pr, _i in r.detalle]
    df = pd.DataFrame(filas).set_index("Momento")
    st.line_chart(df[["Índice €/MWh"]], height=250)
    if curva is not None:
        st.bar_chart(df[["Consumo kWh"]], height=200)

    if diag:
        st.subheader("Diagnóstico: variantes de cálculo más cercanas a lo facturado")
        st.caption("Si una variante distinta del contrato cuadra con la factura, probablemente "
                   "es la que ha usado la comercializadora.")
        st.dataframe(pd.DataFrame(diag), hide_index=True, use_container_width=True)

    datos_factura = {"Comercializadora": ss.get("f_comercializadora"),
                     "Nº factura": ss.get("f_numero"),
                     "Fecha emisión": ss.get("f_emision"),
                     "CUPS": cups, "Tarifa": ss.get("f_tarifa"),
                     "Consumo factura kWh": ss.get("f_consumo"),
                     "Importe SSAA facturado €": ss.get("f_importe"),
                     "Curva": curva.origen if curva is not None else "—"}
    xlsx = informe.generar_excel(r, datos_factura, diag)
    b1, b2 = st.columns(2)
    nombre = "revision_SSAA_%s_%s.xlsx" % (cups or "sin_cups", r.inicio.strftime("%Y-%m"))
    b1.download_button("Descargar informe Excel", xlsx, nombre,
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if b2.button("Guardar en revisiones_ssaa"):
        ruta = informe.guardar_informe(xlsx, r, cups, ss.get("f_numero"))
        st.success("Guardado en %s" % ruta)
