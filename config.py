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


def credencial(nombre_env, nombre_fichero):
    """Lee una credencial de variable de entorno o de un fichero de esta carpeta."""
    valor = os.environ.get(nombre_env, "").strip()
    if valor:
        return valor
    ruta = CARPETA / nombre_fichero
    if ruta.exists():
        return ruta.read_text(encoding="utf-8").strip()
    return ""
