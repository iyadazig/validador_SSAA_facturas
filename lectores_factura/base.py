# -*- coding: utf-8 -*-
"""
Datos comunes de una factura y lector generico.

Cada comercializadora tiene su maqueta. El lector generico saca lo que se
puede reconocer en cualquier factura (CUPS, tarifa, periodo, lineas que
mencionan servicios de ajuste) y los lectores especificos lo afinan. Todo lo
leido se puede corregir en la app antes de calcular: si no se reconoce nada,
la factura se rellena a mano.

Una factura puede traer varias lineas de SSAA, cada una de su propio periodo
(p. ej. Naturgy regulariza en julio los meses de abril, mayo y junio): cada
LineaSSAA lleva su periodo, sus kWh, su precio y su importe, y se revisa aparte.
"""

import datetime as dt
import re
from dataclasses import dataclass, field

# CIF de la comercializadora (mas fiable que el nombre, que puede salir en
# textos legales de otras empresas). Se comparan sin guiones.
CIF_COMERCIALIZADORAS = {
    "A81948077": "Endesa",
    "A08431090": "Naturgy",
}

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
                 "servicios ajuste", "ssaa", "s.s.a.a", "ajustes del sistema",
                 "ajuste del sistema", "sobrecostes de mercado", "sobrecoste de mercado")

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
         "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
         "noviembre": 11, "diciembre": 12}

RE_CUPS = re.compile(r"\bES\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?[A-Z]{2}(?:\s?\d[FPRCXYZ])?\b")
RE_TARIFA = re.compile(r"\b([236])[.,]([0-4])\s?TD(VE)?\b", re.I)
RE_FECHA = r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})"
RE_RANGO = re.compile(RE_FECHA + r"\s*(?:al|a|hasta|-|–|/)\s*" + RE_FECHA, re.I)
RE_PERIODO = re.compile(
    r"(?:del|desde|periodo|período)[^0-9]{0,40}" + RE_FECHA +
    r"\s*(?:al|a|hasta|-|–)\s*" + RE_FECHA, re.I)
RE_EMISION = re.compile(r"fecha\s+(?:de\s+)?(?:emisi[oó]n|factura)[^0-9]{0,15}" + RE_FECHA, re.I)
RE_NUMERO = re.compile(r"n[ºo°.]?\s*(?:de\s+)?factura[:\s]*([A-Z0-9][A-Z0-9/\-]{4,})", re.I)
RE_IMPORTE = re.compile(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+,\d+|-?\d+\.\d+|-?\d+")
RE_KWH = re.compile(r"(-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*kWh", re.I)


@dataclass
class LineaSSAA:
    concepto: str = "Servicios de ajuste"
    inicio: dt.date = None
    fin: dt.date = None
    kwh: float = None
    precio: float = None          # EUR/kWh tal como sale en la factura
    importe: float = None         # EUR
    texto: str = ""

    @property
    def precio_mwh(self):
        return self.precio * 1000 if self.precio is not None else None


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
    lineas_ssaa: list = field(default_factory=list)
    candidatos_kwh: list = field(default_factory=list)
    lector: str = "genérico"
    texto: str = ""
    avisos: list = field(default_factory=list)

    @property
    def importe_ssaa(self):
        imps = [l.importe for l in self.lineas_ssaa if l.importe is not None]
        return round(sum(imps), 2) if imps else None


# --------------------------------------------------------------- utilidades
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
    s = s.strip()
    for f in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y"):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    m = re.match(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", s, re.I)
    if m and m.group(2).lower() in MESES:
        return dt.date(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1)))
    return None


RE_FECHA_LETRA = r"(\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4})"


def texto_pdf(datos):
    """Texto del PDF (bytes) en orden de lectura, pagina a pagina."""
    import fitz
    with fitz.open(stream=datos, filetype="pdf") as doc:
        return "\n".join(p.get_text("text", sort=True) for p in doc)


def detectar_comercializadora(texto):
    sin_guiones = re.sub(r"[\s.-]", "", texto).upper()
    for cif, nombre in CIF_COMERCIALIZADORAS.items():
        if cif in sin_guiones:
            return nombre
    t = texto.lower()
    for nombre, claves in COMERCIALIZADORAS.items():
        if any(c in t for c in claves):
            return nombre
    return ""


def es_linea_ssaa(linea):
    return any(p in linea.lower() for p in PALABRAS_SSAA)


def comprobar_lineas(f):
    """Avisos comunes: cuadre kWh x precio = importe y periodo de cada linea."""
    for l in f.lineas_ssaa:
        if l.inicio is None:
            l.inicio, l.fin = f.inicio, f.fin
        if None not in (l.kwh, l.precio, l.importe):
            calc = l.kwh * l.precio
            if abs(calc - l.importe) > 0.02 + abs(l.importe) * 1e-4:
                f.avisos.append("%s: %s kWh × %s €/kWh = %.2f €, pero la factura pone %.2f €."
                                % (l.concepto, l.kwh, l.precio, calc, l.importe))
    if not f.lineas_ssaa:
        f.avisos.append("No se ha encontrado ninguna línea de servicios de ajuste.")
    return f


# --------------------------------------------------------------- lector generico
def _linea_generica(bloque):
    """kWh, precio e importe de una linea con formato libre."""
    l = LineaSSAA(texto=" ".join(bloque.split()))
    m = RE_KWH.search(bloque)
    resto = bloque
    if m:
        l.kwh = numero_es(m.group(1))
        resto = bloque[m.end():]
    nums = [numero_es(n) for n in RE_IMPORTE.findall(resto)]
    nums = [n for n in nums if n is not None]
    if nums:
        l.importe = nums[-1]
        if len(nums) > 1:
            l.precio = nums[-2]
    r = RE_RANGO.search(bloque)
    if r:
        l.inicio, l.fin = fecha_es(r.group(1)), fecha_es(r.group(2))
    return l


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
        if es_linea_ssaa(linea):
            # a veces los importes caen en la linea siguiente
            bloque = linea if re.search(r"\d,\d", linea) else \
                linea + " " + (lineas[i + 1] if i + 1 < len(lineas) else "")
            f.lineas_ssaa.append(_linea_generica(bloque))
        for m in RE_KWH.finditer(linea):
            v = numero_es(m.group(1))
            if v:
                f.candidatos_kwh.append((v, " ".join(linea.split())))

    if len(f.lineas_ssaa) > 1:
        f.avisos.append("Hay %d líneas que parecen de SSAA: revisa cuáles cuentan."
                        % len(f.lineas_ssaa))
    if f.candidatos_kwh:
        f.consumo_kwh = max(v for v, _ in f.candidatos_kwh)
        f.avisos.append("Consumo tomado como el mayor valor en kWh de la factura: compruébalo.")
    if not f.texto.strip():
        f.avisos.append("El PDF no tiene texto (¿escaneado?): rellena los datos a mano.")
    return comprobar_lineas(f)
