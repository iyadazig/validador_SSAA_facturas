# -*- coding: utf-8 -*-
"""Rutas y parametros comunes del revisor de SSAA."""

import os
from pathlib import Path

CARPETA = Path(__file__).resolve().parent

# Excel historicos de ESIOS (los mantiene el proyecto Descarga_datos_ESIOS).
CARPETA_ESIOS = Path(os.environ.get(
    "SSAA_CARPETA_ESIOS", CARPETA.parent / "Descarga_datos_ESIOS"))

FICHERO_CONTRATOS = CARPETA / "contratos_ssaa.json"
CARPETA_REVISIONES = CARPETA / "revisiones_ssaa"
CARPETA_EJEMPLOS = CARPETA / "facturas_ejemplo"

# Tolerancia por defecto para dar una factura por correcta (% sobre lo recalculado).
TOLERANCIA_PCT = 0.5
# Un SSAA horario por encima de esto se marca como sospechoso (dato de avance roto).
UMBRAL_ANOMALO = 200.0

