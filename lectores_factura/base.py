# -*- coding: utf-8 -*-
"""
Datos comunes de una factura y lector generico.

Cada comercializadora tiene su maqueta. El lector generico saca lo que se
puede reconocer en cualquier factura (CUPS, tarifa, periodo, lineas que
mencionan servicios de ajuste) y los lectores especificos lo afinan. Todo lo
leido se puede corregir en la app antes de calcular: si no se reconoce nada,
la factura se rellena a mano.
"""

import datetime as dt
import re
from dataclasses import dataclass, field

COMERCIALIZADORAS = {
    "Endesa": ("endesa",),
    "Iberdrola": ("iberdrola", "curenergía", "curenergia"),
    "Naturgy": ("naturgy", "gas natural fenosa", "comercializadora regulada gas & power"),
    "Repsol": ("repsol",),
    "TotalEnergies": ("totalenergies", "total energies"),
    "EDP": ("edp comercializadora", "edp energía", "edp energia"),
    "Acciona": ("acciona energía", "acciona green"),
    "Axpo": ("axpo",),
    "Audax": ("audax",),
    "Factor Energía": ("factor energía", "factor energia"),
    "Nexus": ("nexus energía", "nexus energia"),
    "Holaluz": ("holaluz",),
    "Engie": ("engie",),
    "Galp": ("galp",),
    "Cepsa": ("cepsa", "moeve"),
    "Gesternova": ("gesternova",),
    "Aldro": ("aldro",),
    "Fenie": ("fenie energía", "fenie energia"),
}

PALABRAS_SSAA = ("servicios de ajuste", "servicio de ajuste", "serv. ajuste", "serv ajuste",
                 "ssaa", "s.s.a.a", "ajustes del sistema", "ajuste del sistema",
                 "regularización ssaa", "regularizacion ssaa", "regulariz. ssaa")

RE_CUPS = re.compile(r"\bES\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?[A-Z]{2}(?:\s?\d[FPRCXYZ])?\b")
RE_TARIFA = re.compile(r"\b([236])[.,]([0-4])\s?TD(VE)?\b", re.I)
RE_FECHA = r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})"
RE_PERIODO = re.compile(
    r"(?:del|desde|periodo|período)[^0-9]{0,40}" + RE_FECHA +
    r"\s*(?:al|a|hasta|-|–)\s*" + RE_FECHA, re.I)
RE_EMISION = re.compile(r"fecha\s+(?:de\s+)?(?:emisi[oó]n|factura)[^0-9]{0,15}" + RE_FECHA, re.I)
RE_NUMERO = re.compile(r"n[ºo°.]?\s*(?:de\s+)?factura[:\s]*([A-Z0-9][A-Z0-9/\-]{4,})", re.I)
RE_IMPORTE = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{1,6}|-?\d+,\d{1,6}|-?\d+\.\d{1,6}")
RE_KWH = re.compile(r"(-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*kWh", re.I)


@dataclass
class LineaSSAA:
    texto: str
    numeros: list
    importe: float = None


@dataclass
class DatosFactura:
    comercializadora: str = ""
    numero: str = ""
    fecha_emision: dt.date = None
    cups: str = ""
    tarifa: str = ""
    inicio: dt.date = None
    fin: dt.date = None
    consumo_kwh: float = None
    importe_ssaa: float = None
    lineas_ssaa: list = field(default_factory=list)
    candidatos_kwh: list = field(default_factory=list)
    lector: str = "genérico"
    texto: str = ""
    avisos: list = field(default_factory=list)


def numero_es(s):
    """'1.234,56' -> 1234.56 ; '100.000' -> 100000 ; '12.5' -> 12.5"""
    s = s.strip()
    if "," in s or re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", s):
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def fecha_es(s):
    for f in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y"):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def texto_pdf(datos):
    """Texto del PDF (bytes) en orden de lectura, pagina a pagina."""
    import fitz
    with fitz.open(stream=datos, filetype="pdf") as doc:
        return "\n".join(p.get_text("text", sort=True) for p in doc)


def detectar_comercializadora(texto):
    t = texto.lower()
    for nombre, claves in COMERCIALIZADORAS.items():
        if any(c in t for c in claves):
            return nombre
    return ""


def lector_generico(texto):
    f = DatosFactura(texto=texto)
    f.comercializadora = detectar_comercializadora(texto)

    m = RE_CUPS.search(texto)
    if m:
        f.cups = re.sub(r"\s", "", m.group(0))
    m = RE_TARIFA.search(texto)
    if m:
        f.tarifa = "%s.%sTD%s" % (m.group(1), m.group(2), (m.group(3) or "").upper())
    m = RE_PERIODO.search(texto)
    if m:
        f.inicio, f.fin = fecha_es(m.group(1)), fecha_es(m.group(2))
    m = RE_EMISION.search(texto)
    if m:
        f.fecha_emision = fecha_es(m.group(1))
    m = RE_NUMERO.search(texto)
    if m:
        f.numero = m.group(1)

    lineas = texto.splitlines()
    for i, linea in enumerate(lineas):
        if any(p in linea.lower() for p in PALABRAS_SSAA):
            # a veces los importes caen en la linea siguiente
            bloque = linea if RE_IMPORTE.search(linea) else \
                linea + " " + (lineas[i + 1] if i + 1 < len(lineas) else "")
            nums = [numero_es(n) for n in RE_IMPORTE.findall(bloque)]
            nums = [n for n in nums if n is not None]
            f.lineas_ssaa.append(LineaSSAA(texto=" ".join(bloque.split()), numeros=nums,
                                           importe=nums[-1] if nums else None))
        for m in RE_KWH.finditer(linea):
            v = numero_es(m.group(1))
            if v:
                f.candidatos_kwh.append((v, " ".join(linea.split())))

    con_importe = [l for l in f.lineas_ssaa if l.importe is not None]
    if con_importe:
        f.importe_ssaa = round(sum(l.importe for l in con_importe), 2)
        if len(con_importe) > 1:
            f.avisos.append("Hay %d líneas que parecen de SSAA: revisa cuáles cuentan."
                            % len(con_importe))
    else:
        f.avisos.append("No se ha encontrado ninguna línea de servicios de ajuste.")
    if f.candidatos_kwh:
        f.consumo_kwh = max(v for v, _ in f.candidatos_kwh)
        f.avisos.append("Consumo tomado como el mayor valor en kWh de la factura: compruébalo.")
    if not f.texto.strip():
        f.avisos.append("El PDF no tiene texto (¿escaneado?): rellena los datos a mano.")
    return f
