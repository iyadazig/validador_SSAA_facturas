# -*- coding: utf-8 -*-
"""Rutas y parametros comunes del revisor de SSAA."""

import os
import sys
from pathlib import Path

# Como ejecutable (PyInstaller) el codigo se descomprime en una carpeta temporal que
# se borra al cerrar: los DATOS (fichas, revisiones...) van siempre junto al .exe y los
# RECURSOS (logo, icono) se leen del paquete.
EJECUTABLE = getattr(sys, "frozen", False)
if EJECUTABLE:
    CARPETA = Path(os.environ.get("SSAA_CARPETA_PROGRAMA", Path(sys.executable).resolve().parent))
    RECURSOS = Path(getattr(sys, "_MEIPASS", CARPETA))
else:
    CARPETA = Path(__file__).resolve().parent
    RECURSOS = CARPETA

# Excel historicos de ESIOS (los mantiene el proyecto Descarga_datos_ESIOS).
CARPETA_ESIOS = Path(os.environ.get(
    "SSAA_CARPETA_ESIOS", CARPETA.parent / "Descarga_datos_ESIOS"))

# Base de datos compartida (usuarios, fichas, historial). En el servidor se puede llevar a
# otra carpeta con SSAA_CARPETA_DATOS.
CARPETA_DATOS = Path(os.environ.get("SSAA_CARPETA_DATOS", CARPETA))
# fichero de fichas de la version anterior: se importa a la base de datos la primera vez
FICHERO_CONTRATOS = CARPETA / "contratos_ssaa.json"
CARPETA_REVISIONES = CARPETA / "revisiones_ssaa"
CARPETA_EJEMPLOS = CARPETA / "facturas_ejemplo"

# Servidor para todo el equipo (lanzador.py --servidor): sin boton de cerrar la app
MODO_SERVIDOR = os.environ.get("SSAA_MODO_SERVIDOR") == "1"

# Tolerancia por defecto para dar una factura por correcta (% sobre lo recalculado).
TOLERANCIA_PCT = 0.5
# Un SSAA horario por encima de esto se marca como sospechoso (dato de avance roto).
UMBRAL_ANOMALO = 200.0
