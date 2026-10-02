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
import gemweb
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

    st.header("Gemweb")
    cred, origen_cred = gemweb.cargar_credenciales()
    if cred:
        st.success("Credenciales: %s" % origen_cred)
    else:
        st.warning("Sin credenciales de Gemweb.")
    with st.expander("Configurar credenciales"):
        st.caption("Se guardan cifradas en tu perfil de Windows (%APPDATA%\\ValidadorSSAA), "
                   "nunca en la carpeta del programa ni en GitHub.")
        nuevo_id = st.text_input("client_id")
        nuevo_secreto = st.text_input("client_secret", type="password")
        g1, g2 = st.columns(2)
        if g1.button("Guardar", disabled=not (nuevo_id and nuevo_secreto)):
            try:
                gemweb.ClienteGemweb(nuevo_id, nuevo_secreto).comprobar()
            except gemweb.GemwebError as e:
                st.error(str(e))
            else:
                gemweb.guardar_credenciales(nuevo_id, nuevo_secreto)
                st.rerun()
        if g2.button("Probar conexión", disabled=not cred):
            try:
                gemweb.ClienteGemweb(*cred).comprobar()
                st.success("Conexión correcta.")
            except gemweb.GemwebError as e:
                st.error(str(e))

st.title("Revisión de servicios de ajuste (SSAA) en facturas")

# valores iniciales de los campos (los widgets no llevan value= para no chocar
# con los que se rellenan al leer el PDF o al cargar una ficha)
for k, v in {"f_comercializadora": "", "f_numero": "", "f_emision": None, "f_cups": "",
             "f_tarifa": "6.1TD", "f_inicio": None, "f_fin": None, "f_consumo": None}.items():
    ss.setdefault(k, v)
if "c_tarifa" not in ss:
    fijar("c_", motor.Contrato().a_dict())

COLS_LINEAS = ["Concepto", "Inicio", "Fin", "kWh", "Precio €/kWh", "Importe €"]


def tabla_lineas(lineas):
    return pd.DataFrame([{"Concepto": l.concepto, "Inicio": l.inicio, "Fin": l.fin,
                          "kWh": l.kwh, "Precio €/kWh": l.precio, "Importe €": l.importe}
                         for l in lineas], columns=COLS_LINEAS)


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
            ss.lineas_iniciales = tabla_lineas(f.lineas_ssaa)
            ss.pop("resultados", None)
            fijar("f_", {"comercializadora": f.comercializadora, "numero": f.numero,
                         "emision": f.fecha_emision, "cups": f.cups,
                         "tarifa": f.tarifa if f.tarifa in motor.TARIFAS else "6.1TD",
                         "inicio": f.inicio, "fin": f.fin, "consumo": f.consumo_kwh})

leida = ss.get("factura_leida")
if leida is not None and pdf is not None:
    st.caption("Lector usado: **%s**. Revisa y corrige los datos antes de calcular." % leida.lector)
    for a in leida.avisos:
        st.warning(a)
    with st.expander("Texto de las líneas de SSAA en el PDF (%d)" % len(leida.lineas_ssaa)):
        for l in leida.lineas_ssaa:
            st.write("`%s`" % l.texto)
    with st.expander("Texto completo del PDF"):
        st.text(leida.texto)

c1, c2, c3 = st.columns(3)
with c1:
    st.text_input("Comercializadora", key="f_comercializadora")
    st.text_input("Nº de factura", key="f_numero")
    st.date_input("Fecha de emisión", key="f_emision", format="DD/MM/YYYY")
with c2:
    cups = st.text_input("CUPS", key="f_cups").strip().upper()
    st.date_input("Inicio del periodo facturado", key="f_inicio", format="DD/MM/YYYY")
    st.date_input("Fin del periodo facturado (incluido)", key="f_fin", format="DD/MM/YYYY")
with c3:
    st.selectbox("Tarifa de acceso", motor.TARIFAS, key="f_tarifa")
    st.number_input("Energía activa facturada (kWh)", min_value=0.0, format="%.3f",
                    key="f_consumo")

st.subheader("Líneas de SSAA")
st.caption("Una fila por cada concepto de SSAA de la factura, con **su** periodo (las "
           "regularizaciones suelen ser de meses anteriores). Importe negativo si es abono. "
           "Si falta el periodo se usa el de la factura.")
lineas_df = st.data_editor(
    ss.get("lineas_iniciales", pd.DataFrame(columns=COLS_LINEAS)),
    key="editor_lineas_%s" % ss.get("pdf_huella", "manual"), num_rows="dynamic",
    use_container_width=True, hide_index=True,
    column_config={
        "Concepto": st.column_config.TextColumn(width="large"),
        "Inicio": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Fin": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "kWh": st.column_config.NumberColumn(format="%.3f"),
        "Precio €/kWh": st.column_config.NumberColumn(format="%.8f"),
        "Importe €": st.column_config.NumberColumn(format="%.2f")})


def _valor(v):
    if v is None or v is pd.NaT:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def lineas_actuales():
    """Lineas del editor como dicts, con el periodo de la factura si les falta."""
    out = []
    for _, fila in lineas_df.iterrows():
        d = {c: _valor(fila.get(c)) for c in COLS_LINEAS}
        for c in ("Inicio", "Fin"):
            if isinstance(d[c], (pd.Timestamp, dt.datetime)):
                d[c] = d[c].date()
        for c in ("kWh", "Precio €/kWh", "Importe €"):
            if d[c] is not None:
                d[c] = float(d[c])
        d["Inicio"] = d["Inicio"] or ss.get("f_inicio")
        d["Fin"] = d["Fin"] or ss.get("f_fin")
        d["Concepto"] = d["Concepto"] or "Servicios de ajuste"
        if d["kWh"] is None and d["Importe €"] is None:
            continue
        out.append(d)
    return out


lineas = lineas_actuales()
if lineas:
    total = sum(l["Importe €"] or 0 for l in lineas)
    st.caption("Total SSAA facturado en las líneas: **%.2f €**" % total)

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
    st.info("No hay ficha guardada para este CUPS: elige la cláusula tipo, rellena las "
            "referencias y pulsa «Guardar ficha».")

NOMBRES_PLANTILLA = ["(personalizada)"] + list(motor.PLANTILLAS)


def aplicar_plantilla():
    nombre = ss.sel_plantilla
    if nombre in motor.PLANTILLAS:
        fijar("c_", motor.PLANTILLAS[nombre])
        ss.c_plantilla = nombre
        if nombre in motor.PLANTILLAS_PERD_POR_TENSION:
            ss.c_perd_fijo = motor.perd_estandar(ss.get("c_tarifa") or ss.get("f_tarifa"))
    else:
        ss.c_plantilla = ""


ss.setdefault("sel_plantilla", ss.get("c_plantilla") or "(personalizada)")
if ss.get("contrato_cargado") != (cups, ss.get("c_plantilla")):
    # al cargar una ficha, el selector refleja su clausula tipo
    ss.contrato_cargado = (cups, ss.get("c_plantilla"))
    ss.sel_plantilla = ss.get("c_plantilla") or "(personalizada)"
st.selectbox("Cláusula tipo", NOMBRES_PLANTILLA, key="sel_plantilla", on_change=aplicar_plantilla,
             help="Rellena cómo se calcula (índice, pérdidas, 1,015…). Las referencias de "
                  "cada CUPS se introducen abajo.")
if ss.get("c_plantilla") in motor.TEXTO_PLANTILLAS:
    st.caption(motor.TEXTO_PLANTILLAS[ss.c_plantilla])

k1, k2, k3 = st.columns(3)
with k1:
    st.text_input("Comercializadora del contrato", key="c_comercializadora")
    st.text_input("Descripción del contrato", key="c_descripcion")
    opciones(motor.MECANISMOS, ("c_mecanismo", "Tipo de cobertura de SSAA"))
    opciones(motor.INDICES, ("c_indice", "Índice ESIOS"))
    if ss.c_indice == "componentes":
        try:
            cols = esios.columnas_componentes()
        except Exception as e:
            cols = []
            st.error("No se pueden leer las columnas de componentes: %s" % e)
        ss.c_componentes = [c for c in ss.get("c_componentes", []) if c in cols]
        st.multiselect("Componentes que suman", cols, key="c_componentes")
    if ss.c_indice == "pfm_ssaa":
        st.selectbox("¿El contrato indica qué componentes se suman?", [True, False],
                     key="c_componentes_pfm_contrato",
                     format_func=lambda v: "Sí, el contrato indica la suma" if v
                     else "No, el contrato no lo especifica")
        ss.c_componentes_pfm = [c for c in ss.get("c_componentes_pfm", [])
                                if c in esios.COLS_PFM_TODOS]
        if not ss.c_componentes_pfm_contrato:
            ss.c_componentes_pfm = list(esios.COLS_PFM_NATURGY)
        st.multiselect("Componentes del PFMHORAS_COM que se suman", list(esios.COLS_PFM_TODOS),
                       key="c_componentes_pfm",
                       disabled=not ss.c_componentes_pfm_contrato,
                       help="Por defecto, la suma que indica Naturgy en algunos contratos: "
                            "Restricciones + Procesos OS + Desvíos + REER + Importe "
                            "participación servicios.")
        if not ss.c_componentes_pfm_contrato:
            st.caption("Se calcula con la suma habitual de Naturgy y, al revisar, se comprueban "
                       "todas las combinaciones de términos del fichero para ver cuál "
                       "reproduce lo facturado.")
    opciones(motor.AGREGACIONES, ("c_agregacion", "Cómo se agrega el índice"))
with k2:
    mec = ss.c_mecanismo
    if mec == "techo":
        st.number_input("Referencia de SSAA (techo) €/MWh", format="%.3f", key="c_techo")
    if mec == "banda":
        st.number_input("Referencia superior €/MWh", format="%.3f", key="c_ref_superior")
        st.number_input("Referencia inferior €/MWh", format="%.3f", key="c_ref_inferior")
    if mec in ("indexado_techo", "indexado_suelo_techo"):
        st.number_input("Precio máximo €/MWh", format="%.3f", key="c_techo")
    if mec == "indexado_suelo_techo":
        st.number_input("Precio mínimo €/MWh", format="%.3f", key="c_suelo")
    if mec == "fijo":
        st.number_input("Precio fijo €/MWh", format="%.3f", key="c_precio_fijo")
    if mec in ("indexado", "indexado_techo", "indexado_suelo_techo"):
        st.number_input("Prima / fee €/MWh", format="%.3f", key="c_prima")
    st.number_input("Apuntamiento Ap (1 si el contrato no lo tiene)", format="%.4f",
                    step=0.01, key="c_apuntamiento")
    st.number_input("Factor final (1,015 = impuesto municipal / HL)", format="%.4f",
                    step=0.001, key="c_factor")
with k3:
    opciones(motor.PERDIDAS, ("c_perdidas", "Pérdidas"))
    if ss.c_perdidas == "fijo":
        st.number_input("Coeficiente de pérdidas %", format="%.3f", key="c_perd_fijo")
    elif ss.c_perdidas != "ninguna" and ss.c_agregacion != "horaria":
        opciones(motor.PERD_AGREGACIONES, ("c_perd_agregacion", "Cómo se agregan las pérdidas"))
    st.selectbox("Tarifa para las pérdidas", motor.TARIFAS, key="c_tarifa")
    st.selectbox("Zona", ["Península", "Baleares", "Canarias"], key="c_zona")
    st.selectbox("Liquidación de ESIOS que fija el contrato", motor.LIQUIDACIONES,
                 key="c_liquidacion_requerida",
                 format_func=lambda v: v or "No la fija (la última publicada)")
    opciones(motor.PERIODOS_CALCULO, ("c_periodo_calculo", "Periodo de cálculo"))
    opciones(motor.REGULARIZACIONES_PERIODO, ("c_regularizacion", "Regularización"))


def contrato_actual():
    d = {k[2:]: v for k, v in ss.items() if k.startswith("c_")}
    d["cups"] = cups
    return motor.Contrato.desde_dict(d)


def errores_ficha(c):
    if c.mecanismo == "techo" and not c.techo:
        return "Falta la Referencia de SSAA (techo)."
    if c.mecanismo == "banda":
        if not (c.ref_superior and c.ref_inferior):
            return "Faltan las referencias superior e inferior de la banda."
        if c.ref_inferior > c.ref_superior:
            return "La referencia inferior es mayor que la superior."
    return None


if st.button("Guardar ficha de contrato", disabled=not cups):
    ficha = contrato_actual()
    error = errores_ficha(ficha)
    if error:
        st.error(error)
    else:
        informe.guardar_contrato(ficha)
        st.success("Ficha guardada para %s: %s." % (cups, motor.MECANISMOS[ficha.mecanismo]))

if ss.c_mecanismo == "banda":
    st.caption("Banda: cargo = consumo × (SSAA − ref. sup.) × (1+perd) × factor si supera la "
               "referencia superior; abono = consumo × (ref. inf. − SSAA) × (1+perd) × factor "
               "si queda por debajo. El abono se calcula con signo negativo.")
elif ss.c_mecanismo == "techo":
    st.caption("Techo: cargo = consumo × (SSAA − referencia) × (1+perd) × factor solo si los "
               "SSAA superan la referencia; por debajo no hay ajuste ni abono.")

guardados = informe.cargar_contratos()
if guardados:
    with st.expander("Fichas de contrato guardadas (%d)" % len(guardados)):
        st.dataframe(pd.DataFrame([{
            "CUPS": c.cups, "Comercializadora": c.comercializadora,
            "Descripción": c.descripcion, "Tarifa": c.tarifa,
            "Cobertura": motor.MECANISMOS.get(c.mecanismo, c.mecanismo),
            "Techo €/MWh": c.techo if c.mecanismo == "techo" else None,
            "Ref. superior €/MWh": c.ref_superior if c.mecanismo == "banda" else None,
            "Ref. inferior €/MWh": c.ref_inferior if c.mecanismo == "banda" else None,
            "Índice": motor.INDICES.get(c.indice, c.indice),
            "Componentes": (" + ".join(c.componentes_pfm) +
                            ("" if c.componentes_pfm_contrato else " (no especificado)"))
            if c.indice == "pfm_ssaa" else None,
            "Pérdidas": motor.PERDIDAS.get(c.perdidas), "Ap": c.apuntamiento,
            "Factor": c.factor, "Regularización": c.regularizacion}
            for c in guardados.values()]), hide_index=True, use_container_width=True)

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
    fechas = [l[c] for l in lineas for c in ("Inicio", "Fin") if l[c]] or \
        [d for d in (ss.get("f_inicio"), ss.get("f_fin")) if d]
    g_ini, g_fin = (min(fechas), max(fechas)) if fechas else (None, None)
    clave_g = (cups, g_ini, g_fin)
    if cups and g_ini and g_fin:
        st.caption("Se descargará del %s al %s (cubre todas las líneas de SSAA)."
                   % (g_ini.strftime("%d/%m/%Y"), g_fin.strftime("%d/%m/%Y")))
    if not (cups and g_ini and g_fin):
        st.info("Rellena el CUPS y el periodo de la factura para descargar la curva.")
    elif not gemweb.cargar_credenciales()[0]:
        st.warning("Configura las credenciales de Gemweb en la barra lateral.")
    elif st.button("Descargar curva de Gemweb"):
        barra = st.progress(0.0, "Conectando con Gemweb…")
        try:
            cliente = gemweb.ClienteGemweb.desde_configuracion()
            c_g, sum_g = cliente.curva(cups, g_ini, g_fin, lambda n, t, a, b: barra.progress(
                n / t, "Descargando %s – %s (%d/%d)" % (a.strftime("%d/%m/%Y"),
                                                       b.strftime("%d/%m/%Y"), n, t)))
        except gemweb.GemwebError as e:
            st.error(str(e))
        else:
            ss.curva_gemweb = (clave_g, c_g, sum_g)
        barra.empty()
    if ss.get("curva_gemweb") and ss.curva_gemweb[0] == clave_g:
        _clave, curva, sum_g = ss.curva_gemweb
        st.write("Suministro en Gemweb: tarifa **%s**, alta %s. Curva **cuartohoraria**, "
                 "%d cuartos, %s a %s, total **%.1f kWh**."
                 % (sum_g.get("tarifa_acces") or sum_g.get("tarifa") or "—",
                    sum_g.get("data_alta") or "—",
                    len(curva.valores), curva.inicio, curva.fin, curva.total_kwh))
        for a in curva.avisos[:10]:
            st.warning(a)

# =================================================================== resultado
st.header("4. Resultado")
colores = {"CORRECTO": "green", "FACTURADO DE MÁS": "red", "FACTURADO DE MENOS": "orange"}
incompletas = [l["Concepto"] for l in lineas if not (l["Inicio"] and l["Fin"])]
if incompletas:
    st.info("Faltan fechas en: %s" % ", ".join(str(c) for c in incompletas))

def partir_por_meses(l, contrato):
    """Si el contrato calcula por mes natural, parte la linea en sus meses. El importe
    facturado queda en la linea original (se compara en los totales)."""
    meses = list(esios.meses_entre(l["Inicio"], l["Fin"]))
    if contrato.periodo_calculo != "mensual" or len(meses) <= 1:
        return [l]
    dias_total = (l["Fin"] - l["Inicio"]).days + 1
    out = []
    for m in meses:
        fin_mes = (dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1) - dt.timedelta(days=1))
        a, b = max(l["Inicio"], m), min(l["Fin"], fin_mes)
        dias = (b - a).days + 1
        parte = dict(l, Inicio=a, Fin=b, Concepto="%s — %s" % (l["Concepto"], m.strftime("%m/%Y")),
                     **{"Importe €": None, "Precio €/kWh": None})
        if curva is not None:
            parte["kWh"] = None           # consumo real del mes, de la curva
        elif l["kWh"] is not None:
            parte["kWh"] = l["kWh"] * dias / dias_total
            parte["avisos"] = ["Consumo del mes prorrateado por días a partir de la línea "
                               "(%d de %d días). Con la curva se usaría el consumo real del mes."
                               % (dias, dias_total)]
        out.append(parte)
    return out


def trimestre(fecha):
    return "%dT %d" % ((fecha.month - 1) // 3 + 1, fecha.year)


def totales(resultados, contrato):
    """Totales por linea de factura (si se partio por meses) y por trimestre."""
    grupos = []
    por_linea = {}
    for l, r, _d in resultados:
        por_linea.setdefault(l["linea"], []).append((l, r))
    partidas = {k: v for k, v in por_linea.items() if len(v) > 1}
    for k, v in partidas.items():
        fact = next((x["Importe €"] for x in lineas[k - 1:k]), None)
        grupos.append(("Línea %d: %s" % (k, lineas[k - 1]["Concepto"]), v, fact))
    if contrato.regularizacion == "trimestral":
        por_tri = {}
        for k, v in por_linea.items():
            por_tri.setdefault(trimestre(v[0][0]["Inicio"]), []).append(k)
        for tri, ks in por_tri.items():
            v = [x for k in ks for x in por_linea[k]]
            facts = [lineas[k - 1]["Importe €"] for k in ks]
            fact = sum(f for f in facts if f is not None) if any(f is not None for f in facts) else None
            grupos.append(("Regularización trimestral %s" % tri, v, fact))
    filas = []
    for nombre, v, fact in grupos:
        rec = sum(r.importe for _l, r in v)
        dif, pct, ver = motor.veredicto(fact, rec, tolerancia)
        filas.append({"Total": nombre, "Meses / líneas": len(v),
                      "MWh": round(sum(r.energia_mwh for _l, r in v), 3),
                      "Facturado €": fact, "Recalculado €": round(rec, 2),
                      "Diferencia €": round(dif, 2) if dif is not None else None,
                      "Diferencia %": round(pct, 2) if pct is not None else None,
                      "Veredicto": ver})
    return filas


if st.button("Revisar SSAA", type="primary", disabled=not lineas or bool(incompletas)):
    contrato = contrato_actual()
    resultados = []
    partes = []
    for n_l, l in enumerate(lineas, 1):
        kwh = l["kWh"]
        if kwh is None and (l["Inicio"], l["Fin"]) == (ss.get("f_inicio"), ss.get("f_fin")):
            kwh = ss.get("f_consumo")
        partes.extend(partir_por_meses(dict(l, kWh=kwh, linea=n_l), contrato))
    with st.spinner("Leyendo ESIOS y calculando…"):
        for l in partes:
            kwh = l["kWh"]
            try:
                r = motor.revisar(contrato, l["Inicio"], l["Fin"], kwh, l["Importe €"],
                                  curva, tolerancia)
                diag = motor.diagnostico(contrato, l["Inicio"], l["Fin"], kwh,
                                         l["Importe €"], curva)
            except motor.ErrorRevision as e:
                resultados.append((l, None, str(e)))
            else:
                for a_ in l.get("avisos", []):
                    r.avisos.insert(0, a_)
                resultados.append((l, r, diag))
        grupos = {}
        for l in partes:
            grupos.setdefault(l["linea"], []).append((l["Inicio"], l["Fin"], l["kWh"]))
        ss.componentes = motor.comprobar_componentes(
            contrato, [(tramos, lineas[n - 1]["Importe €"]) for n, tramos in grupos.items()],
            curva)
    ss.resultados = resultados


def fila_resumen(l, r):
    precio_fact = l["Precio €/kWh"] * 1000 if l["Precio €/kWh"] is not None else (
        l["Importe €"] / r.energia_mwh if r.energia_mwh and l["Importe €"] is not None else None)
    return {"Concepto": l["Concepto"],
            "Periodo": "%s – %s" % (r.inicio.strftime("%d/%m/%Y"), r.fin.strftime("%d/%m/%Y")),
            "MWh": round(r.energia_mwh, 3),
            "Facturado €/MWh": round(precio_fact, 6) if precio_fact is not None else None,
            "Recalculado €/MWh": round(r.precio_efectivo, 6),
            "Facturado €": r.facturado, "Recalculado €": round(r.importe, 2),
            "Diferencia €": round(r.diferencia, 2) if r.diferencia is not None else None,
            "Diferencia %": round(r.diferencia_pct, 2) if r.diferencia_pct is not None else None,
            "Veredicto": r.veredicto}


if ss.get("resultados"):
    validos = [(l, r, d) for l, r, d in ss.resultados if r is not None]
    for l, r, err in ss.resultados:
        if r is None:
            st.error("%s: %s" % (l["Concepto"], err))
    if validos:
        resumen = [fila_resumen(l, r) for l, r, _d in validos]
        tot_f = sum(r.facturado or 0 for _l, r, _d in validos)
        tot_r = sum(r.importe for _l, r, _d in validos)
        m = st.columns(3)
        m[0].metric("Total facturado", "%.2f €" % tot_f)
        m[1].metric("Total recalculado", "%.2f €" % tot_r)
        m[2].metric("Diferencia (facturado − recalculado)", "%+.2f €" % (tot_f - tot_r))
        st.dataframe(pd.DataFrame(resumen), hide_index=True, use_container_width=True)
        filas_tot = totales(validos, validos[0][1].contrato)
        if filas_tot:
            st.markdown("**Totales**")
            st.dataframe(pd.DataFrame(filas_tot), hide_index=True, use_container_width=True)
        comp = ss.get("componentes") or []
        if comp:
            c0 = validos[0][1].contrato
            st.markdown("**Comprobación de componentes del PFMHORAS_COM**")
            concl = motor.conclusion_componentes(comp, c0)
            if concl:
                {"ok": st.success, "aviso": st.warning, "error": st.error}[concl[0]](concl[1])
            if not c0.componentes_pfm_contrato:
                st.caption("El contrato no especifica la suma: el veredicto de arriba usa "
                           "%s." % " + ".join(c0.componentes_pfm))
            st.dataframe(pd.DataFrame(motor.tabla_componentes(comp)), hide_index=True,
                         use_container_width=True)

    for i, (l, r, diag) in enumerate(validos, 1):
        with st.expander("%d. %s — :%s[%s]" % (i, l["Concepto"], colores.get(r.veredicto, "gray"),
                                               r.veredicto), expanded=len(validos) == 1):
            m = st.columns(4)
            m[0].metric("Índice medio aritmético", "%.6f €/MWh" % r.indice_medio)
            m[1].metric("Índice ponderado", "%.6f €/MWh" % r.indice_ponderado
                        if r.indice_ponderado is not None else "—")
            m[2].metric("Precio aplicado", "%.6f €/MWh" % r.precio_aplicado)
            m[3].metric("Pérdidas aplicadas", "%.4f %%" % r.perd_aplicada)
            for a in r.avisos:
                st.warning(a)
            st.caption("Datos ESIOS: " + "; ".join("%s: %s" % kv for kv in r.liquidaciones.items()))
            st.markdown("**Fórmulas aplicadas**")
            st.code("\n".join(motor.formula_clausula(r.contrato)), language=None)
            st.markdown("**Cálculo paso a paso**")
            st.dataframe(pd.DataFrame([{
                "Paso": p["paso"], "Concepto": p["concepto"], "Fórmula": p["formula"],
                "Sustitución": p["sustitucion"],
                "Resultado": p["valor"] if isinstance(p["valor"], str) else
                motor._f(p["valor"], 2 if p["unidad"] == "€" else 9 if p["unidad"] == "€/kWh"
                         else 0 if p["unidad"] in ("horas", "cuartos") else 6),
                "Unidad": p["unidad"]} for p in motor.pasos_calculo(r)]),
                hide_index=True, use_container_width=True)
            filas = [{"Momento": dt.datetime.combine(k[0], dt.time()) + dt.timedelta(
                          minutes=(k[1] - 1) * 60 + ((k[2] - 1) * 15 if len(k) == 3 else 0)),
                      "Índice €/MWh": v, "Consumo kWh": e}
                     for k, e, v, _p, _pr, _i in r.detalle]
            df = pd.DataFrame(filas).set_index("Momento")
            st.line_chart(df[["Índice €/MWh"]], height=220)
            if curva is not None:
                st.bar_chart(df[["Consumo kWh"]], height=180)
            if diag:
                st.markdown("**Diagnóstico**: variantes de cálculo más cercanas a lo facturado. "
                            "Si una distinta del contrato cuadra, probablemente es la que ha "
                            "usado la comercializadora.")
                st.dataframe(pd.DataFrame(diag), hide_index=True, use_container_width=True)

    if validos:
        datos_factura = {"Comercializadora": ss.get("f_comercializadora"),
                         "Nº factura": ss.get("f_numero"),
                         "Fecha emisión": ss.get("f_emision"),
                         "CUPS": cups, "Tarifa": ss.get("f_tarifa"),
                         "Periodo facturado": "%s – %s" % (ss.get("f_inicio"), ss.get("f_fin")),
                         "Energía facturada kWh": ss.get("f_consumo"),
                         "Curva": curva.origen if curva is not None else "—"}
        xlsx = informe.generar_excel([(fila_resumen(l, r), r, d) for l, r, d in validos],
                                     datos_factura, totales(validos, validos[0][1].contrato),
                                     ss.get("componentes") or [])
        b1, b2 = st.columns(2)
        nombre = "revision_SSAA_%s_%s.xlsx" % (cups or "sin_cups", ss.get("f_numero") or "")
        b1.download_button("Descargar informe Excel", xlsx, nombre,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if b2.button("Guardar en revisiones_ssaa"):
            ruta = informe.guardar_informe(xlsx, validos[0][1], cups, ss.get("f_numero"))
            st.success("Guardado en %s" % ruta)
