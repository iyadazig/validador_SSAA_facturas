# -*- coding: utf-8 -*-
"""
MOTOR DE REVISION DE SSAA
=========================
Recalcula el importe de servicios de ajuste de una factura a partir de la
clausula del contrato y de los datos de ESIOS, y lo compara con lo facturado.

Clausula (Contrato):
  indice       sah_pvpc   Total SAH del PVPC_DETALLE (horario, EUR/MWh bc)
               ssaa_esios TOTAL SSAA del Excel de componentes (cuartohorario)
               componentes suma de columnas elegidas del Excel de componentes
               fijo       precio fijo de contrato
  agregacion   media_aritmetica | media_ponderada (por consumo) | horaria
               (horaria = se aplica hora a hora, o cuarto a cuarto con curva QH)
  mecanismo    techo        regularizacion: cargo +(indice - techo) si lo supera,
                            0 si no (cobertura hasta una Referencia de SSAA; sin abono)
               banda        regularizacion: +(indice - ref_superior) si lo supera,
                            -(ref_inferior - indice) si queda por debajo, 0 dentro
               indexado     precio = indice + prima
               indexado_techo       precio = min(indice, techo) + prima
               indexado_suelo_techo precio = max(suelo, min(indice, techo)) + prima
               fijo         precio = precio_fijo
  perdidas     ninguna | liquicomun_h | liquicomun_qh | pvpc | fijo
  perd_agregacion  como se agrega PERD cuando la agregacion no es horaria
  factor       multiplicador final (1,015 = impuesto municipal)

importe = energia MWh x precio x (1 + perd/100) x factor
"""

import datetime as dt
import itertools
from dataclasses import dataclass, field, asdict

import config
import ssaa_datos_esios as esios

INDICES = {"sah_pvpc": "Total SAH PVPC (horario, bc)",
           "ssaa_esios": "Total SSAA ESIOS (cuartohorario)",
           "componentes": "Suma de componentes ESIOS",
           "fijo": "Precio fijo de contrato"}
AGREGACIONES = {"media_aritmetica": "Media aritmética del periodo",
                "media_ponderada": "Media ponderada por consumo",
                "horaria": "Hora a hora (indexado puro)"}
MECANISMOS = {"techo": "Techo: cargo si los SSAA superan la referencia",
              "banda": "Banda: cargo por encima y abono por debajo",
              "indexado": "Indexado (índice + prima)",
              "indexado_techo": "Indexado con precio máximo",
              "indexado_suelo_techo": "Indexado con precio mínimo y máximo",
              "fijo": "Precio fijo"}
# mecanismos que son una regularizacion sobre un precio de SSAA ya incluido
REGULARIZACIONES = ("techo", "banda")
PERDIDAS = {"ninguna": "Sin pérdidas",
            "liquicomun_h": "PERD tarifa liquicomún (horario)",
            "liquicomun_qh": "PERD tarifa liquicomún (cuartohorario)",
            "pvpc": "PERD del PVPC",
            "fijo": "Coeficiente fijo"}
PERD_AGREGACIONES = {"media_aritmetica": "Media aritmética",
                     "media_ponderada": "Media ponderada por consumo"}
TARIFAS = ["2.0TD", "3.0TD", "3.0TDVE", "6.1TD", "6.1TDVE", "6.2TD", "6.3TD", "6.4TD"]

# Clausulas tipo: fijan como se calcula; las referencias de cada CUPS se rellenan aparte.
PLANTILLAS = {
    "Endesa grandes cuentas — techo": dict(
        comercializadora="Endesa", mecanismo="techo", indice="sah_pvpc",
        agregacion="media_aritmetica", perdidas="liquicomun_h",
        perd_agregacion="media_aritmetica", factor=1.015, prima=0.0),
    "Endesa grandes cuentas — banda": dict(
        comercializadora="Endesa", mecanismo="banda", indice="sah_pvpc",
        agregacion="media_aritmetica", perdidas="liquicomun_h",
        perd_agregacion="media_aritmetica", factor=1.015, prima=0.0),
}
TEXTO_PLANTILLAS = {
    "Endesa grandes cuentas — techo":
        "Cobertura hasta la Referencia de SSAA. Si la media aritmética del Total SAH "
        "(PVPC_DETALLE_DD) del periodo la supera: cargo = consumo MWh × (SSAA reales − "
        "referencia) × (1 + perd) × 1,015. Si no, no hay ajuste.",
    "Endesa grandes cuentas — banda":
        "Banda entre referencia inferior y superior. Si SSAA reales > ref. superior: cargo = "
        "consumo × (SSAA reales − ref. sup.) × (1 + perd) × 1,015; si < ref. inferior: abono = "
        "consumo × (ref. inf. − SSAA reales) × (1 + perd) × 1,015. Perd = media aritmética de "
        "las pérdidas horarias.",
}


@dataclass
class Contrato:
    cups: str = ""
    descripcion: str = ""
    comercializadora: str = ""
    plantilla: str = ""
    tarifa: str = "6.1TD"
    zona: str = "Península"
    indice: str = "sah_pvpc"
    componentes: list = field(default_factory=list)
    agregacion: str = "media_aritmetica"
    mecanismo: str = "techo"
    precio_fijo: float = 0.0
    prima: float = 0.0
    ref_superior: float = 0.0
    ref_inferior: float = 0.0
    techo: float = 0.0
    suelo: float = 0.0
    perdidas: str = "ninguna"
    perd_fijo: float = 0.0
    perd_agregacion: str = "media_aritmetica"
    factor: float = 1.0

    @classmethod
    def desde_dict(cls, d):
        campos = cls.__dataclass_fields__
        out = {}
        for k, v in d.items():
            if k not in campos:
                continue
            if campos[k].type is float and v is not None:
                v = float(v)
            out[k] = v
        return cls(**out)

    def a_dict(self):
        return asdict(self)


@dataclass
class Resultado:
    contrato: Contrato
    inicio: dt.date
    fin: dt.date
    energia_mwh: float
    indice_medio: float          # media aritmetica del indice en el periodo
    indice_ponderado: float      # media ponderada por consumo (None sin curva)
    indice_aplicado: float       # el que entra en la formula (agregado o ponderado)
    precio_aplicado: float       # EUR/MWh tras el mecanismo, antes de perdidas
    perd_aplicada: float         # % (agregada o ponderada)
    importe: float
    facturado: float = None
    diferencia: float = None
    diferencia_pct: float = None
    veredicto: str = ""
    resolucion: str = "h"
    detalle: list = field(default_factory=list)
    avisos: list = field(default_factory=list)
    liquidaciones: dict = field(default_factory=dict)
    tolerancia_pct: float = config.TOLERANCIA_PCT

    @property
    def precio_efectivo(self):
        """EUR/MWh de importe final por MWh consumido."""
        return self.importe / self.energia_mwh if self.energia_mwh else 0.0


class ErrorRevision(Exception):
    pass


# --------------------------------------------------------------------- mecanismo
def aplicar_mecanismo(c, indice):
    m = c.mecanismo
    if m == "techo":
        return max(indice - c.techo, 0.0)
    if m == "indexado":
        return indice + c.prima
    if m == "indexado_techo":
        return min(indice, c.techo) + c.prima
    if m == "indexado_suelo_techo":
        return max(c.suelo, min(indice, c.techo)) + c.prima
    if m == "banda":
        if indice > c.ref_superior:
            return indice - c.ref_superior
        if indice < c.ref_inferior:
            return -(c.ref_inferior - indice)
        return 0.0
    if m == "fijo":
        return c.precio_fijo
    raise ErrorRevision("Mecanismo desconocido: %s" % m)


# ------------------------------------------------------------------------ series
def _indice(c, ini, fin, resolucion):
    """Serie del indice en la resolucion pedida y liquidaciones usadas."""
    if c.indice == "sah_pvpc":
        serie = {k: v["sah"] for k, v in esios.pvpc_horario(ini, fin).items()}
        return serie, {"PVPC_DETALLE": "date_type=datos (definitivo)"}
    if c.indice in ("ssaa_esios", "componentes"):
        cols = [esios.COL_TOTAL_SSAA] if c.indice == "ssaa_esios" else c.componentes
        if not cols:
            raise ErrorRevision("No se han elegido componentes para el índice")
        serie, liq = esios.componentes_qh(ini, fin, cols)
        return (serie if resolucion == "qh" else esios.a_horario(serie)), liq
    if c.indice == "fijo":
        # sin indice: la rejilla horaria la da el PVPC si existe, si no la curva
        try:
            serie = {k: c.precio_fijo for k in esios.pvpc_horario(ini, fin)}
        except esios.SinDatos:
            serie = {}
        return serie, {}
    raise ErrorRevision("Índice desconocido: %s" % c.indice)


def _perdidas(c, ini, fin):
    """Funcion clave -> PERD %."""
    if c.perdidas == "ninguna":
        return lambda k: 0.0
    if c.perdidas == "fijo":
        return lambda k: c.perd_fijo
    if c.perdidas == "pvpc":
        s = {k: v["perd"] for k, v in esios.pvpc_horario(ini, fin).items()}
    elif c.perdidas == "liquicomun_h":
        s = esios.perdidas_horarias(ini, fin, c.tarifa, c.zona)
    elif c.perdidas == "liquicomun_qh":
        s = esios.perdidas_qh(ini, fin, c.tarifa)
        if s:
            horaria = esios.a_horario(s)
            return lambda k: s.get(k) if len(k) == 3 else horaria.get(k)
    else:
        raise ErrorRevision("Pérdidas desconocidas: %s" % c.perdidas)
    if not s:
        raise ErrorRevision("No hay pérdidas '%s' para %s en los Excel"
                            % (PERDIDAS[c.perdidas], c.tarifa))
    return lambda k: s.get(k[:2])


def _curva_en(curva, resolucion):
    """Curva {clave: kWh} llevada a la resolucion del calculo."""
    if curva is None:
        return None
    valores = curva.valores
    if curva.resolucion == resolucion:
        return valores
    if curva.resolucion == "qh" and resolucion == "h":
        out = {}
        for (f, h, _q), v in valores.items():
            out[(f, h)] = out.get((f, h), 0.0) + v
        return out
    raise ErrorRevision("La curva es horaria y el cálculo pide cuartohoraria")


def _media(valores):
    return sum(valores) / len(valores) if valores else 0.0


def _ponderada(pares):
    e = sum(p for p, _ in pares)
    return sum(p * v for p, v in pares) / e if e else None


# ------------------------------------------------------------------------- motor
def revisar(contrato, inicio, fin, consumo_kwh=None, facturado=None, curva=None,
            tolerancia_pct=config.TOLERANCIA_PCT):
    """Recalcula el SSAA del periodo [inicio, fin] (ambos incluidos)."""
    c = contrato
    avisos = []
    if fin < inicio:
        raise ErrorRevision("La fecha final es anterior a la inicial")
    necesita_curva = c.agregacion in ("media_ponderada", "horaria") or \
        c.perd_agregacion == "media_ponderada" and c.perdidas not in ("ninguna", "fijo")
    if necesita_curva and curva is None:
        raise ErrorRevision("Esta cláusula necesita la curva de consumo (%s)"
                            % AGREGACIONES[c.agregacion])

    # resolucion: cuartohoraria solo si curva QH, indice QH y calculo hora a hora
    resolucion = "h"
    if (curva is not None and curva.resolucion == "qh" and c.agregacion == "horaria"
            and c.indice in ("ssaa_esios", "componentes")):
        resolucion = "qh"

    try:
        indice, liquidaciones = _indice(c, inicio, fin, resolucion)
        perd = _perdidas(c, inicio, fin)
    except esios.SinDatos as e:
        raise ErrorRevision(str(e))
    if not indice and c.indice == "fijo" and curva is not None:
        indice = {k: c.precio_fijo for k in _curva_en(curva, resolucion)}
    if not indice:
        raise ErrorRevision("No hay datos de %s entre %s y %s en %s"
                            % (INDICES[c.indice], inicio, fin, config.CARPETA_ESIOS))

    faltan = esios.dias_sin_datos(indice, inicio, fin)
    if faltan:
        avisos.append("Faltan %d día(s) de %s en los Excel (primero %s, último %s). "
                      "Actualiza el histórico antes de dar la revisión por buena."
                      % (len(faltan), INDICES[c.indice], faltan[0], faltan[-1]))
    raros = sorted({k[0] for k, v in indice.items() if abs(v) > config.UMBRAL_ANOMALO})
    if raros:
        avisos.append("Valores del índice por encima de %.0f €/MWh en: %s. "
                      "Suelen ser datos de avance erróneos de ESIOS."
                      % (config.UMBRAL_ANOMALO, ", ".join(str(d) for d in raros)))
    for mes, liq in liquidaciones.items():
        if isinstance(liq, str) and liq.startswith("A"):
            avisos.append("%s: dato de avance (%s), aún no liquidado por REE." % (mes, liq))

    claves = sorted(indice)
    cv = _curva_en(curva, resolucion)
    if cv is not None:
        sin = [k for k in claves if k not in cv]
        if sin:
            avisos.append("La curva no tiene %d %s del periodo (se toman como 0 kWh)."
                          % (len(sin), "cuartos" if resolucion == "qh" else "horas"))
        e_curva = sum(cv.get(k, 0.0) for k in claves)
        if consumo_kwh:
            dif = (e_curva - consumo_kwh) / consumo_kwh * 100
            if abs(dif) > 1:
                avisos.append("La curva suma %.0f kWh y la factura %.0f kWh (%+.2f %%)."
                              % (e_curva, consumo_kwh, dif))
    else:
        e_curva = None

    perds = []
    for k in claves:
        p = perd(k)
        if p is None:
            p = 0.0
            perds.append(None)
        else:
            perds.append(p)
    if None in perds:
        avisos.append("Faltan pérdidas en %d %s (se toman como 0 %%)."
                      % (perds.count(None), "cuartos" if resolucion == "qh" else "horas"))
    perds = [p or 0.0 for p in perds]
    consumos = [cv.get(k, 0.0) for k in claves] if cv is not None else [None] * len(claves)
    valores = [indice[k] for k in claves]

    indice_medio = _media(valores)
    indice_pond = _ponderada(list(zip(consumos, valores))) if cv is not None else None

    detalle = []
    if c.agregacion == "horaria":
        importe = 0.0
        for k, e, v, p in zip(claves, consumos, valores, perds):
            precio = aplicar_mecanismo(c, v)
            imp = e / 1000.0 * precio * (1 + p / 100.0) * c.factor
            importe += imp
            detalle.append((k, e, v, p, precio, imp))
        energia = (e_curva or 0.0) / 1000.0
        indice_aplicado = indice_pond if indice_pond is not None else indice_medio
        perd_aplicada = _ponderada(list(zip(consumos, perds))) or 0.0
        precio_aplicado = importe / energia / (1 + perd_aplicada / 100) / c.factor \
            if energia else 0.0
    else:
        energia = (consumo_kwh if consumo_kwh else (e_curva or 0.0)) / 1000.0
        if not energia:
            raise ErrorRevision("Falta el consumo de la factura")
        indice_aplicado = indice_pond if c.agregacion == "media_ponderada" else indice_medio
        if c.perdidas == "fijo":
            perd_aplicada = c.perd_fijo
        elif c.perd_agregacion == "media_ponderada" and cv is not None:
            perd_aplicada = _ponderada(list(zip(consumos, perds))) or 0.0
        else:
            perd_aplicada = _media(perds)
        precio_aplicado = aplicar_mecanismo(c, indice_aplicado)
        importe = energia * precio_aplicado * (1 + perd_aplicada / 100.0) * c.factor
        detalle = [(k, e, v, p, None, None) for k, e, v, p in zip(claves, consumos, valores, perds)]

    r = Resultado(contrato=c, inicio=inicio, fin=fin, energia_mwh=energia,
                  indice_medio=indice_medio, indice_ponderado=indice_pond,
                  indice_aplicado=indice_aplicado, precio_aplicado=precio_aplicado,
                  perd_aplicada=perd_aplicada, importe=importe, resolucion=resolucion,
                  detalle=detalle, avisos=avisos, liquidaciones=liquidaciones)
    comparar(r, facturado, tolerancia_pct)
    return r


def comparar(r, facturado, tolerancia_pct=config.TOLERANCIA_PCT):
    if facturado is None:
        r.veredicto = "Sin importe facturado para comparar"
        return r
    r.facturado = facturado
    r.tolerancia_pct = tolerancia_pct
    r.diferencia = facturado - r.importe
    base = abs(r.importe) if r.importe else None
    r.diferencia_pct = r.diferencia / base * 100 if base else None
    if abs(r.diferencia) < 0.01 or (r.diferencia_pct is not None
                                    and abs(r.diferencia_pct) <= tolerancia_pct):
        r.veredicto = "CORRECTO"
    elif r.diferencia > 0:
        r.veredicto = "FACTURADO DE MÁS"
    else:
        r.veredicto = "FACTURADO DE MENOS"
    return r


# ------------------------------------------------------------ formulas y pasos
NOMBRE_INDICE = {"sah_pvpc": "SAHh (Total SAH horario del PVPC_DETALLE_DD, €/MWh bc)",
                 "ssaa_esios": "SSAAh (TOTAL SSAA de ESIOS; valor horario = media de sus 4 cuartos)",
                 "componentes": "SSAAh (suma de los componentes elegidos; horario = media de sus 4 cuartos)",
                 "fijo": "Precio fijo"}
NOMBRE_PERD = {"liquicomun_h": "PERDh (pérdidas horarias de la tarifa %s, liquicomún)",
               "liquicomun_qh": "PERDqh (pérdidas cuartohorarias de la tarifa %s, liquicomún)",
               "pvpc": "PERDh (coeficiente de pérdidas del PVPC)"}


def formula_mecanismo(c, x="SSAA reales"):
    """Formula en texto del precio (o diferencia) que aplica el mecanismo."""
    m = c.mecanismo
    if m == "techo":
        return "Diferencia = MAX(%s − Ref. SSAA ; 0)" % x
    if m == "banda":
        return ("Diferencia = %s − Ref. superior si %s > Ref. superior; "
                "−(Ref. inferior − %s) si %s < Ref. inferior; 0 en otro caso" % (x, x, x, x))
    if m == "indexado":
        return "Precio = %s + Prima" % x
    if m == "indexado_techo":
        return "Precio = MIN(%s ; Precio máximo) + Prima" % x
    if m == "indexado_suelo_techo":
        return "Precio = MAX(Precio mínimo ; MIN(%s ; Precio máximo)) + Prima" % x
    return "Precio = Precio fijo de contrato"


def formula_clausula(c):
    """Lineas de texto con las formulas de la clausula."""
    ind = NOMBRE_INDICE[c.indice]
    out = []
    if c.agregacion == "horaria":
        out.append("Importe = Σh [ Eh/1000 × P(SSAAh) × (1 + PERDh/100) × Factor ]")
        out.append("P(SSAAh): " + formula_mecanismo(c, "SSAAh"))
        out.append("Eh = consumo de la hora (o cuarto) en kWh, de la curva; " + ind)
    else:
        if c.agregacion == "media_ponderada":
            out.append("SSAA reales = Σ(Eh × SSAAh) / Σ Eh   (media ponderada por consumo)")
        else:
            out.append("SSAA reales = Σ SSAAh / N   (media aritmética de las N horas del periodo)")
        out.append("SSAAh = " + ind)
        out.append(formula_mecanismo(c))
        out.append("Importe = Consumo real MWh × %s × (1 + perd/100) × Factor"
                   % ("Diferencia" if c.mecanismo in REGULARIZACIONES else "Precio"))
    if c.perdidas in NOMBRE_PERD:
        nombre = NOMBRE_PERD[c.perdidas] % c.tarifa if "%s" in NOMBRE_PERD[c.perdidas] \
            else NOMBRE_PERD[c.perdidas]
        if c.agregacion == "horaria":
            out.append("PERDh = " + nombre)
        elif c.perd_agregacion == "media_ponderada":
            out.append("perd = Σ(Eh × PERDh) / Σ Eh, con " + nombre)
        else:
            out.append("perd = Σ PERDh / N   (media aritmética), con " + nombre)
    elif c.perdidas == "fijo":
        out.append("perd = %s %% (coeficiente fijo de contrato)" % _f(c.perd_fijo, 4))
    else:
        out.append("perd = 0 (sin pérdidas)")
    out.append("Factor = %s%s" % (_f(c.factor, 4), " (impuesto municipal 1,5 %)"
                                  if abs(c.factor - 1.015) < 1e-9 else ""))
    return out


def _f(v, d=6):
    """Numero con coma decimal para los textos."""
    if v is None:
        return "—"
    return ("%.*f" % (d, v)).replace(".", ",")


def pasos_calculo(r):
    """Calculo paso a paso: [{paso, clave, concepto, formula, sustitucion, valor, unidad}].
    `clave` identifica el paso para que el informe Excel ponga su formula viva."""
    c = r.contrato
    pasos = []

    def paso(clave, concepto, formula, sustitucion, valor, unidad=""):
        pasos.append({"paso": len(pasos) + 1, "clave": clave, "concepto": concepto,
                      "formula": formula, "sustitucion": sustitucion, "valor": valor,
                      "unidad": unidad})

    vals = [v for _k, _e, v, _p, _pr, _i in r.detalle]
    perds = [p for _k, _e, _v, p, _pr, _i in r.detalle]
    cons = [e or 0.0 for _k, e, _v, _p, _pr, _i in r.detalle]
    n = len(vals)
    unidad_n = "cuartos" if r.resolucion == "qh" else "horas"
    paso("n", "Número de %s del periodo" % unidad_n, "N = %s del %s al %s" % (
        unidad_n, r.inicio.strftime("%d/%m/%Y"), r.fin.strftime("%d/%m/%Y")), "", n, unidad_n)

    if c.agregacion == "horaria":
        paso("mwh", "Consumo real (curva)", "Consumo = Σ Eh / 1000",
             "%s kWh / 1000" % _f(sum(cons), 3), r.energia_mwh, "MWh")
        paso("ssaa", "SSAA medio ponderado (informativo)", "Σ(Eh × SSAAh) / Σ Eh", "",
             r.indice_ponderado, "€/MWh")
        paso("importe", "Importe recalculado",
             "Σh [ Eh/1000 × P(SSAAh) × (1 + PERDh/100) × Factor ];  " +
             formula_mecanismo(c, "SSAAh"),
             "suma de la columna Importe de la hoja de detalle", r.importe, "€")
        paso("precio_ef", "Precio efectivo", "Importe / Consumo",
             "%s / %s" % (_f(r.importe, 2), _f(r.energia_mwh, 6)), r.precio_efectivo, "€/MWh")
    else:
        if c.agregacion == "media_ponderada":
            paso("ssaa", "SSAA reales (media ponderada)", "Σ(Eh × SSAAh) / Σ Eh",
                 "%s / %s" % (_f(sum(e * v for e, v in zip(cons, vals)), 4), _f(sum(cons), 3)),
                 r.indice_aplicado, "€/MWh")
        else:
            paso("ssaa", "SSAA reales (media aritmética)", "Σ SSAAh / N",
                 "%s / %d" % (_f(sum(vals), 4), n), r.indice_aplicado, "€/MWh")
        if c.perdidas == "fijo":
            paso("perd", "Pérdidas (perd)", "Coeficiente fijo de contrato", "",
                 r.perd_aplicada, "%")
        elif c.perdidas == "ninguna":
            paso("perd", "Pérdidas (perd)", "Sin pérdidas", "", 0.0, "%")
        elif c.perd_agregacion == "media_ponderada":
            paso("perd", "Pérdidas (perd, media ponderada)", "Σ(Eh × PERDh) / Σ Eh",
                 "%s / %s" % (_f(sum(e * p for e, p in zip(cons, perds)), 4), _f(sum(cons), 3)),
                 r.perd_aplicada, "%")
        else:
            paso("perd", "Pérdidas (perd, media aritmética)", "Σ PERDh / N",
                 "%s / %d" % (_f(sum(perds), 4), n), r.perd_aplicada, "%")

        x = _f(r.indice_aplicado)
        m = c.mecanismo
        if m == "techo":
            sust = "MAX(%s − %s ; 0)" % (x, _f(c.techo, 3))
        elif m == "banda":
            if r.indice_aplicado > c.ref_superior:
                sust = "%s − %s (supera la ref. superior: cargo)" % (x, _f(c.ref_superior, 3))
            elif r.indice_aplicado < c.ref_inferior:
                sust = "−(%s − %s) (por debajo de la ref. inferior: abono)" % (_f(c.ref_inferior, 3), x)
            else:
                sust = "%s está entre %s y %s: sin regularización" % (
                    x, _f(c.ref_inferior, 3), _f(c.ref_superior, 3))
        elif m == "indexado":
            sust = "%s + %s" % (x, _f(c.prima, 3))
        elif m == "indexado_techo":
            sust = "MIN(%s ; %s) + %s" % (x, _f(c.techo, 3), _f(c.prima, 3))
        elif m == "indexado_suelo_techo":
            sust = "MAX(%s ; MIN(%s ; %s)) + %s" % (_f(c.suelo, 3), x, _f(c.techo, 3), _f(c.prima, 3))
        else:
            sust = _f(c.precio_fijo, 3)
        paso("precio", "Diferencia sobre la referencia" if m in REGULARIZACIONES
             else "Precio de SSAA", formula_mecanismo(c), sust, r.precio_aplicado, "€/MWh")
        precio_final = r.precio_aplicado * (1 + r.perd_aplicada / 100) * c.factor
        paso("precio_final", "Precio final con pérdidas y factor",
             "%s × (1 + perd/100) × Factor" % ("Diferencia" if m in REGULARIZACIONES else "Precio"),
             "%s × (1 + %s/100) × %s" % (_f(r.precio_aplicado), _f(r.perd_aplicada, 4),
                                         _f(c.factor, 4)), precio_final, "€/MWh")
        paso("precio_kwh", "Precio final en €/kWh", "Precio final / 1000",
             "%s / 1000" % _f(precio_final), precio_final / 1000, "€/kWh")
        paso("mwh", "Consumo real", "Consumo kWh / 1000",
             "%s / 1000" % _f(r.energia_mwh * 1000, 3), r.energia_mwh, "MWh")
        paso("importe", "Importe recalculado", "Consumo MWh × Precio final",
             "%s × %s" % (_f(r.energia_mwh), _f(precio_final)), r.importe, "€")

    if r.facturado is not None:
        paso("facturado", "Importe facturado", "Importe de la línea en la factura", "",
             r.facturado, "€")
        paso("dif", "Diferencia", "Facturado − Recalculado",
             "%s − %s" % (_f(r.facturado, 2), _f(r.importe, 2)), r.diferencia, "€")
        paso("dif_pct", "Diferencia relativa", "Diferencia / |Recalculado| × 100",
             "%s / %s × 100" % (_f(r.diferencia, 2), _f(abs(r.importe), 2)),
             r.diferencia_pct, "%")
        paso("veredicto", "Veredicto",
             "CORRECTO si |Diferencia| < 0,01 € o |Diferencia %%| ≤ %s %%; si no, de más o "
             "de menos según el signo" % _f(r.tolerancia_pct, 2), "", r.veredicto)
    return pasos


# ---------------------------------------------------------------- diagnostico
def diagnostico(contrato, inicio, fin, consumo_kwh, facturado, curva=None, maximo=8):
    """Recalcula con variantes razonables de la clausula y ordena por cercania
    a lo facturado. Sirve para entender como ha calculado la comercializadora."""
    if facturado is None:
        return []
    base = contrato.a_dict()
    indices = ["sah_pvpc", "ssaa_esios"]
    if contrato.indice not in indices:
        indices.append(contrato.indice)
    agregaciones = ["media_aritmetica"] + (["media_ponderada", "horaria"] if curva else [])
    if contrato.agregacion not in agregaciones:
        agregaciones.append(contrato.agregacion)
    perdidas = ["ninguna", "liquicomun_h", "pvpc"]
    if contrato.perdidas not in perdidas:
        perdidas.append(contrato.perdidas)
    factores = sorted({1.0, 1.015, contrato.factor})

    filas = []
    for ind, agr, per, fac in itertools.product(indices, agregaciones, perdidas, factores):
        if contrato.mecanismo == "fijo" and ind != contrato.indice:
            continue
        var = Contrato.desde_dict(dict(base, indice=ind, agregacion=agr, perdidas=per,
                                       factor=fac))
        try:
            r = revisar(var, inicio, fin, consumo_kwh, facturado, curva)
        except ErrorRevision:
            continue
        cambios = [n for n, a, b in (("índice", ind, contrato.indice),
                                     ("agregación", agr, contrato.agregacion),
                                     ("pérdidas", per, contrato.perdidas),
                                     ("factor", fac, contrato.factor)) if a != b]
        filas.append({"Índice": INDICES[ind], "Agregación": AGREGACIONES[agr],
                      "Pérdidas": PERDIDAS[per], "Factor": fac,
                      "Importe €": round(r.importe, 2),
                      "Dif. con facturado €": round(r.diferencia, 2),
                      "Cambia respecto al contrato": ", ".join(cambios) or "(contrato)"})
    filas.sort(key=lambda f: abs(f["Dif. con facturado €"]))
    return filas[:maximo]
