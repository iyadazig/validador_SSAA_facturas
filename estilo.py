# -*- coding: utf-8 -*-
"""
Imagen corporativa GE&PE para la app: colores, tipografia, logo y textos en
espanol de los elementos que Streamlit muestra en ingles.
"""

import base64

import streamlit as st

import config

GRANATE = "#970000"          # rojo del logo
GRANATE_OSCURO = "#8B1A1A"   # plantilla del informe diario
NEGRO = "#1E1E1E"
GRIS = "#5A534C"
GRIS_CLARO = "#8A837C"
BEIS = "#FAF7F4"
BEIS_BORDE = "#E6E0DA"
ROSA = "#F3D9D9"
VERDE = "#2E7D32"
AMBAR = "#B26A00"

LOGO = config.CARPETA / "assets" / "logo_geype.png"
LOGO_PEQ = config.CARPETA / "assets" / "logo_geype_peq.png"
ICONO = config.CARPETA / "assets" / "icono.ico"

COLOR_VEREDICTO = {"CORRECTO": VERDE, "FACTURADO DE MÁS": GRANATE,
                   "FACTURADO DE MENOS": AMBAR}

CSS = """
<style>
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select {
    font-family: Arial, Helvetica, sans-serif !important;
}
/* barra superior de Streamlit: sin texto en ingles */
[data-testid="stStatusWidget"], [data-testid="stDecoration"], [data-testid="stMainMenu"],
[data-testid="stToolbar"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.2rem; max-width: 1400px; }

/* cabecera corporativa */
.gp-cabecera {
    display: flex; align-items: center; gap: 1.6rem;
    border-bottom: 4px solid %(granate)s; padding: 0.4rem 0 1rem 0; margin-bottom: 1.4rem;
}
.gp-cabecera img { height: 74px; }
.gp-cabecera h1 {
    font-size: 1.75rem; font-weight: 700; color: %(negro)s; margin: 0; padding: 0;
    letter-spacing: 0.01em;
}
.gp-cabecera p { color: %(gris)s; margin: 0.25rem 0 0 0; font-size: 0.95rem; }

/* titulos de seccion numerados */
.gp-seccion {
    display: flex; align-items: center; gap: 0.7rem;
    margin: 1.8rem 0 0.8rem 0; padding-bottom: 0.45rem; border-bottom: 1px solid %(borde)s;
}
.gp-seccion .num {
    background: %(granate)s; color: #fff; font-weight: 700; border-radius: 50%%;
    width: 1.9rem; height: 1.9rem; display: flex; align-items: center; justify-content: center;
    font-size: 1rem; flex: none;
}
.gp-seccion .tit { font-size: 1.3rem; font-weight: 700; color: %(negro)s; }
.gp-seccion .sub { color: %(gris_claro)s; font-size: 0.9rem; margin-left: auto; }

/* subtitulos */
h3, .stMarkdown h3 {
    color: %(granate_oscuro)s !important; font-weight: 700 !important; font-size: 1.12rem !important;
    padding-top: 0.6rem !important;
}

/* tarjetas de metricas */
[data-testid="stMetric"] {
    background: %(beis)s; border: 1px solid %(borde)s; border-left: 4px solid %(granate)s;
    border-radius: 6px; padding: 0.7rem 0.9rem;
}
[data-testid="stMetricLabel"] { color: %(gris)s; }
[data-testid="stMetricValue"] { color: %(negro)s; font-weight: 700; }

/* veredicto */
.gp-veredicto {
    display: inline-block; padding: 0.35rem 0.9rem; border-radius: 4px; color: #fff;
    font-weight: 700; letter-spacing: 0.03em; font-size: 0.95rem;
}

/* botones */
.stButton > button, .stDownloadButton > button {
    border-radius: 4px; font-weight: 600; border: 1px solid %(granate)s; color: %(granate)s;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background: %(rosa)s; color: %(granate_oscuro)s; border-color: %(granate_oscuro)s;
}
.stButton > button[kind="primary"] { background: %(granate)s; color: #fff; }
.stButton > button[kind="primary"]:hover { background: %(granate_oscuro)s; color: #fff; }

/* barra lateral */
[data-testid="stSidebar"] { background: %(beis)s; border-right: 1px solid %(borde)s; }
[data-testid="stSidebar"] h2 { color: %(granate_oscuro)s; font-size: 1.05rem; }

/* expanders */
[data-testid="stExpander"] details { border: 1px solid %(borde)s; border-radius: 6px; }
[data-testid="stExpander"] summary:hover { color: %(granate)s; }

/* subida de ficheros: textos en espanol */
[data-testid="stFileUploaderDropzoneInstructions"] > div > span { display: none; }
[data-testid="stFileUploaderDropzoneInstructions"] > div::before {
    content: "Arrastra el archivo aquí"; display: block; color: %(negro)s;
}
[data-testid="stFileUploaderDropzoneInstructions"] > div > small { display: none; }
[data-testid="stFileUploaderDropzoneInstructions"] > div::after {
    content: "Hasta 200 MB por archivo"; display: block; font-size: 0.8rem; color: %(gris_claro)s;
}
[data-testid="stFileUploaderDropzone"] button { font-size: 0 !important; }
[data-testid="stFileUploaderDropzone"] button::after {
    content: "Buscar archivo"; font-size: 0.9rem;
}
[data-testid="stFileUploaderDropzone"] { background: %(beis)s; border: 1px dashed %(borde)s; }

/* pie */
.gp-pie {
    margin-top: 3rem; padding-top: 0.8rem; border-top: 1px solid %(borde)s;
    color: %(gris_claro)s; font-size: 0.8rem; text-align: center;
}
</style>
""" % {"granate": GRANATE, "granate_oscuro": GRANATE_OSCURO, "negro": NEGRO, "gris": GRIS,
       "gris_claro": GRIS_CLARO, "beis": BEIS, "borde": BEIS_BORDE, "rosa": ROSA}


# Textos fijos de los componentes de Streamlit (en ingles y sin opcion de idioma).
# Solo se sustituyen nodos cuyo texto coincide EXACTAMENTE, para no tocar datos.
TRADUCCIONES = {
    "Browse files": "Buscar archivo", "Drag and drop file here": "Arrastra el archivo aquí",
    "Add row": "Añadir fila", "Delete row": "Borrar fila", "Delete rows": "Borrar filas",
    "Search": "Buscar", "Download as CSV": "Descargar CSV", "Fullscreen": "Pantalla completa",
    "Close fullscreen": "Salir de pantalla completa", "Show/hide columns": "Mostrar u ocultar columnas",
    "No results": "Sin resultados", "Choose an option": "Elige una opción",
    "Choose options": "Elige opciones", "Clear all": "Borrar todo",
    "No options to select.": "No hay opciones.", "Remove": "Quitar",
    "Sort ascending": "Orden ascendente", "Sort descending": "Orden descendente",
    "Format": "Formato", "Autosize": "Ajustar ancho", "Pin column": "Fijar columna",
    "Unpin column": "Soltar columna", "Hide column": "Ocultar columna",
    "Press the down arrow key to interact with the calendar and select a date. Press the escape "
    "button to close the calendar.": "Pulsa la flecha abajo para abrir el calendario y elegir una "
    "fecha. Pulsa Escape para cerrarlo.",
    "Select a date.": "Elige una fecha.", "Running...": "Calculando…",
    "Mo": "Lu", "Tu": "Ma", "We": "Mi", "Th": "Ju", "Fr": "Vi", "Sa": "Sá", "Su": "Do",
}
MESES_EN = ["January", "February", "March", "April", "May", "June", "July", "August",
            "September", "October", "November", "December"]
MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
            "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def traducir():
    """Traduce en el navegador los textos fijos en ingles de los widgets (calendario,
    subida de ficheros, tabla editable, desplegables) y el formato de fecha."""
    import json
    import streamlit.components.v1 as components
    components.html("""<script>
    const T = %s, EN = %s, ES = %s;
    const doc = window.parent.document;
    const reMes = new RegExp("^(" + EN.join("|") + ")( \\\\d{4})?$");
    function nodo(n) {
        const t = n.nodeValue.trim();
        if (!t) return;
        if (T[t] !== undefined) { n.nodeValue = n.nodeValue.replace(t, T[t]); return; }
        const m = t.match(reMes);
        if (m) n.nodeValue = n.nodeValue.replace(m[1], ES[EN.indexOf(m[1])]);
    }
    function pasar(raiz) {
        const w = doc.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
        let n; while ((n = w.nextNode())) nodo(n);
        raiz.querySelectorAll && raiz.querySelectorAll("input[placeholder], [aria-label]").forEach(e => {
            if (e.placeholder === "DD/MM/YYYY") e.placeholder = "DD/MM/AAAA";
            const a = e.getAttribute("aria-label");
            if (a && T[a] !== undefined) e.setAttribute("aria-label", T[a]);
        });
    }
    pasar(doc.body);
    // en cada ejecucion se sustituye el observador anterior (su iframe puede haberse borrado)
    if (window.parent.__gpTraductor) window.parent.__gpTraductor.disconnect();
    window.parent.__gpTraductor = new MutationObserver(ms => ms.forEach(m => {
        m.addedNodes.forEach(n => n.nodeType === 3 ? nodo(n) : (n.nodeType === 1 && pasar(n)));
        if (m.type === "characterData") nodo(m.target);
    }));
    window.parent.__gpTraductor.observe(doc.body, {childList: true, subtree: true,
                                                   characterData: true});
    </script>""" % (json.dumps(TRADUCCIONES, ensure_ascii=False), json.dumps(MESES_EN),
                    json.dumps(MESES_ES, ensure_ascii=False)), height=0)


def _b64(ruta):
    return base64.b64encode(ruta.read_bytes()).decode("ascii")


def aplicar():
    """CSS corporativo y logo en la barra lateral. Llamar justo tras set_page_config."""
    st.markdown(CSS, unsafe_allow_html=True)
    if LOGO_PEQ.exists():
        st.logo(str(LOGO_PEQ), size="large")


def cabecera(titulo, subtitulo=""):
    logo = '<img src="data:image/png;base64,%s" alt="GE&PE">' % _b64(LOGO_PEQ) \
        if LOGO_PEQ.exists() else ""
    st.markdown('<div class="gp-cabecera">%s<div><h1>%s</h1><p>%s</p></div></div>'
                % (logo, titulo, subtitulo), unsafe_allow_html=True)


def seccion(numero, titulo, subtitulo=""):
    st.markdown('<div class="gp-seccion"><span class="num">%s</span><span class="tit">%s</span>'
                '<span class="sub">%s</span></div>' % (numero, titulo, subtitulo),
                unsafe_allow_html=True)


def veredicto(texto):
    color = COLOR_VEREDICTO.get(texto, GRIS_CLARO)
    return '<span class="gp-veredicto" style="background:%s">%s</span>' % (color, texto)


def pie():
    traducir()
    st.markdown('<div class="gp-pie">GE&amp;PE · Ingeniería y Gestión Energética — Revisión de '
                'servicios de ajuste. Los datos se procesan en este equipo.</div>',
                unsafe_allow_html=True)
