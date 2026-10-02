# -*- coding: utf-8 -*-
"""
LANZADOR DEL REVISOR DE SSAA (lo que ejecuta "Revisor SSAA.exe")
================================================================
Arranca la app de Streamlit solo para este equipo (localhost) y abre el
navegador. Si ya estaba abierta, solo vuelve a abrir el navegador.
Se cierra con el boton "Cerrar la aplicacion" de la barra lateral.

Tambien se puede probar sin compilar:   python lanzador.py
"""

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

PUERTO = 8765
URL = "http://localhost:%d" % PUERTO


def en_marcha():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PUERTO)) == 0


def abrir_navegador_cuando_este_lista():
    for _ in range(240):
        if en_marcha():
            webbrowser.open(URL)
            return
        time.sleep(0.25)


def autoprueba():
    """Revisor SSAA.exe --autoprueba: comprueba que el ejecutable lee ESIOS, lee facturas,
    calcula y genera grafica e informe. Escribe autoprueba_resultado.txt junto al .exe."""
    import datetime as dt
    import traceback
    destino = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    os.environ["SSAA_CARPETA_PROGRAMA"] = str(destino)
    sys.path.insert(0, str(Path(getattr(sys, "_MEIPASS", destino))))
    lineas = []

    def paso(nombre, funcion):
        t = time.time()
        try:
            res = funcion()
            lineas.append("OK    %-28s %5.1f s  %s" % (nombre, time.time() - t, res))
        except Exception:
            lineas.append("FALLO %-28s\n%s" % (nombre, traceback.format_exc()))

    import config
    lineas.append("Datos en %s | ESIOS en %s" % (config.CARPETA, config.CARPETA_ESIOS))
    import ssaa_motor as m
    import graficos
    import informe
    c = m.Contrato.desde_dict(dict(m.PLANTILLAS["Endesa grandes cuentas — techo (PVPC)"], techo=18.0))
    r = {}
    paso("Leer ESIOS y calcular", lambda: r.setdefault(
        "r", m.revisar(c, dt.date(2026, 8, 1), dt.date(2026, 8, 31), 10000, 10.0)).veredicto)
    paso("PFMHORAS_COM (Naturgy)", lambda: round(m.revisar(m.Contrato.desde_dict(dict(
        m.PLANTILLAS["Naturgy — regularización trimestral (banda)"], ref_superior=18,
        ref_inferior=15, perd_fijo=7)), dt.date(2026, 4, 1), dt.date(2026, 4, 30), 10000,
        None).indice_medio, 4))
    paso("Grafica", lambda: len(graficos.grafico_ssaa(r["r"]).to_dict()["datasets"]))
    paso("Informe Excel", lambda: "%d bytes" % len(informe.generar_excel(
        [({"Concepto": "x", "Periodo": "x", "Veredicto": r["r"].veredicto}, r["r"], [])],
        {"CUPS": "prueba"})))
    paso("Fichas de contrato", lambda: "%d fichas" % len(informe.cargar_contratos()))
    pdfs = sorted(config.CARPETA_EJEMPLOS.glob("*.pdf"))
    if pdfs:
        from lectores_factura import leer_factura
        paso("Leer PDF (%s)" % pdfs[0].name[:18], lambda: "%s, %d línea(s)" % (
            leer_factura(pdfs[0].read_bytes()).lector,
            len(leer_factura(pdfs[0].read_bytes()).lineas_ssaa)))
    (destino / "autoprueba_resultado.txt").write_text("\n".join(lineas), encoding="utf-8")


def main():
    if "--autoprueba" in sys.argv:
        autoprueba()
        return
    if en_marcha():
        webbrowser.open(URL)
        return
    recursos = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    if getattr(sys, "frozen", False):
        # los datos (fichas, revisiones) junto al .exe, no en la carpeta temporal
        os.environ["SSAA_CARPETA_PROGRAMA"] = str(Path(sys.executable).resolve().parent)
    os.chdir(recursos)          # Streamlit lee .streamlit/config.toml de aqui

    from streamlit.web import bootstrap
    opciones = {
        "server.port": PUERTO,
        "server.address": "localhost",        # solo este equipo, no la red
        "server.headless": True,
        "server.fileWatcherType": "none",
        "global.developmentMode": False,
        "browser.gatherUsageStats": False,
        "client.toolbarMode": "viewer",
        "theme.base": "light",
        "theme.primaryColor": "#970000",
        "theme.backgroundColor": "#FFFFFF",
        "theme.secondaryBackgroundColor": "#F5F1EC",
        "theme.textColor": "#1E1E1E",
        "theme.font": "sans serif",
    }
    bootstrap.load_config_options(flag_options=opciones)
    threading.Thread(target=abrir_navegador_cuando_este_lista, daemon=True).start()
    bootstrap.run(str(recursos / "app_revision_ssaa.py"), False, [], opciones)


if __name__ == "__main__":
    main()
