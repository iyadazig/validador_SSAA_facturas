# -*- coding: utf-8 -*-
"""python -m unittest discover tests"""

import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import curva_consumo
import ssaa_datos_esios as esios
import ssaa_motor as motor

D = dt.date(2026, 4, 1)


def pvpc_falso(sah_por_hora, perd=10.0, horas=24):
    """PVPC de un dia con SAH = f(hora)."""
    return lambda ini, fin: {(D, h): {"sah": sah_por_hora(h), "perd": perd}
                             for h in range(1, horas + 1)}


def curva(valores, resolucion="h"):
    return curva_consumo.Curva(resolucion=resolucion, valores=valores)


class Mecanismos(unittest.TestCase):
    def c(self, **kw):
        base = dict(ref_superior=18.0, ref_inferior=14.0, techo=20, suelo=10)
        base.update(kw)
        return motor.Contrato(**base)

    def test_banda(self):
        c = self.c(mecanismo="banda")
        self.assertAlmostEqual(motor.aplicar_mecanismo(c, 25.0), 25 - 18.0)
        self.assertEqual(motor.aplicar_mecanismo(c, 15.0), 0.0)
        self.assertAlmostEqual(motor.aplicar_mecanismo(c, 12.0), -(14.0 - 12))

    def test_techo_solo_cargo(self):
        self.assertEqual(motor.aplicar_mecanismo(self.c(mecanismo="techo"), 30), 10)
        self.assertEqual(motor.aplicar_mecanismo(self.c(mecanismo="techo"), 15), 0)

    def test_indexado_con_limites(self):
        self.assertEqual(motor.aplicar_mecanismo(self.c(mecanismo="indexado_techo"), 30), 20)
        self.assertEqual(motor.aplicar_mecanismo(self.c(mecanismo="indexado_techo"), 15), 15)
        self.assertEqual(motor.aplicar_mecanismo(self.c(mecanismo="indexado_suelo_techo"), 5), 10)

    def test_plantillas_validas(self):
        for nombre, valores in motor.PLANTILLAS.items():
            c = motor.Contrato.desde_dict(dict(valores, plantilla=nombre))
            self.assertIn(c.mecanismo, motor.REGULARIZACIONES)
            self.assertIn(nombre, motor.TEXTO_PLANTILLAS)
        self.assertEqual(motor.aplicar_mecanismo(self.c(mecanismo="indexado", prima=1), 5), 6)


class Revision(unittest.TestCase):
    def test_banda_media_aritmetica(self):
        # SAH 20 todas las horas, 1000 kWh, PERD 10 %: (20-18) x 1 MWh x 1,1 x 1,015
        with mock.patch.object(esios, "pvpc_horario", pvpc_falso(lambda h: 20.0)):
            c = motor.Contrato(mecanismo="banda", ref_superior=18.0, ref_inferior=14.0,
                               factor=1.015, perdidas="pvpc")
            r = motor.revisar(c, D, D, 1000, None)
        self.assertAlmostEqual(r.importe, 2.0 * 1.1 * 1.015)

    def test_indexado_horario_igual_a_ponderado_si_lineal(self):
        sah = lambda h: float(h)
        cv = curva({(D, h): 10.0 * h for h in range(1, 25)})
        with mock.patch.object(esios, "pvpc_horario", pvpc_falso(sah, perd=0)):
            hor = motor.revisar(motor.Contrato(mecanismo="indexado", agregacion="horaria"),
                                D, D, None, None, cv)
            pon = motor.revisar(motor.Contrato(mecanismo="indexado",
                                               agregacion="media_ponderada"),
                                D, D, cv.total_kwh, None, cv)
        esperado = sum(10.0 * h * h for h in range(1, 25)) / 1000
        self.assertAlmostEqual(hor.importe, esperado)
        self.assertAlmostEqual(pon.importe, esperado)

    def test_dia_de_25_horas(self):
        cv = curva({(D, h): 1.0 for h in range(1, 26)})
        with mock.patch.object(esios, "pvpc_horario", pvpc_falso(lambda h: 10.0, 0, 25)):
            r = motor.revisar(motor.Contrato(mecanismo="indexado", agregacion="horaria"),
                              D, D, 25, None, cv)
        self.assertAlmostEqual(r.importe, 25 / 1000 * 10)
        self.assertEqual(len(r.detalle), 25)
        self.assertFalse([a for a in r.avisos if "curva" in a])

    def test_veredicto(self):
        with mock.patch.object(esios, "pvpc_horario", pvpc_falso(lambda h: 20.0, 0)):
            c = motor.Contrato(mecanismo="indexado")
            self.assertEqual(motor.revisar(c, D, D, 1000, 20.0).veredicto, "CORRECTO")
            self.assertEqual(motor.revisar(c, D, D, 1000, 25.0).veredicto, "FACTURADO DE MÁS")
            self.assertEqual(motor.revisar(c, D, D, 1000, 15.0).veredicto, "FACTURADO DE MENOS")

    def test_pasos_cuadran_con_el_importe(self):
        cv = curva({(D, h): 10.0 for h in range(1, 25)})
        with mock.patch.object(esios, "pvpc_horario", pvpc_falso(lambda h: 15.0 + h, perd=5)):
            for kw in (dict(mecanismo="techo", techo=20, perdidas="pvpc", factor=1.015),
                       dict(mecanismo="banda", ref_superior=40, ref_inferior=30, perdidas="pvpc"),
                       dict(mecanismo="indexado", prima=1, agregacion="horaria", perdidas="pvpc")):
                c = motor.Contrato(**kw)
                r = motor.revisar(c, D, D, 240, 10.0, cv)
                pasos = {p["clave"]: p for p in motor.pasos_calculo(r)}
                self.assertAlmostEqual(pasos["importe"]["valor"], r.importe)
                self.assertEqual(pasos["veredicto"]["valor"], r.veredicto)
                if c.agregacion != "horaria":
                    self.assertAlmostEqual(pasos["mwh"]["valor"] * pasos["precio_final"]["valor"],
                                           r.importe)
                self.assertTrue(motor.formula_clausula(c))

    def test_sin_curva_cuando_hace_falta(self):
        c = motor.Contrato(agregacion="horaria")
        with self.assertRaises(motor.ErrorRevision):
            motor.revisar(c, D, D, 1000, None)


class CurvaFichero(unittest.TestCase):
    def test_csv_datadis_hora_final(self):
        filas = ["CUPS;Fecha;Hora;Consumo_kWh;Metodo_obtencion"]
        filas += ["ES0031;01/04/2026;%02d:00;%s;Real" % (h, str(h).replace(".", ","))
                  for h in range(1, 25)]
        c = curva_consumo.leer_curva("\n".join(filas).encode(), "curva.csv")
        self.assertEqual(c.resolucion, "h")
        self.assertEqual(c.valores[(D, 1)], 1.0)
        self.assertEqual(c.valores[(D, 24)], 24.0)
        self.assertEqual(c.inicio, D)

    def test_csv_cuartohorario_inicio(self):
        filas = ["fecha y hora,kWh"]
        t = dt.datetime(2026, 4, 1)
        for i in range(96):
            filas.append("%s,%d" % ((t + dt.timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M"), i))
        c = curva_consumo.leer_curva("\n".join(filas).encode(), "qh.csv")
        self.assertEqual(c.resolucion, "qh")
        self.assertEqual(c.valores[(D, 1, 1)], 0)
        self.assertEqual(c.valores[(D, 24, 4)], 95)


@unittest.skipUnless((config.CARPETA_ESIOS / "2026_Historico_PVPC_horario.xlsx").exists(),
                     "sin Excel de ESIOS")
@unittest.skipUnless((config.CARPETA_ESIOS / "2026_Historico_componentes_ESIOS.xlsx").exists(),
                     "sin Excel de ESIOS")
class PFMHorasReales(unittest.TestCase):
    """Clausula trimestral con datos publicos del PFMHORAS_COM y una banda generica."""
    MESES = [(dt.date(2026, 4, 1), dt.date(2026, 4, 30), 100000.0),
             (dt.date(2026, 5, 1), dt.date(2026, 5, 31), 120000.0)]

    def contrato(self, **kw):
        n = "Naturgy — regularización trimestral (banda)"
        base = dict(motor.PLANTILLAS[n], plantilla=n, ref_superior=18.0, ref_inferior=15.0,
                    perd_fijo=motor.perd_estandar("6.1TD"), tarifa="6.1TD")
        base.update(kw)
        return motor.Contrato.desde_dict(base)

    def test_formula(self):
        c = self.contrato(componentes_pfm=["Restricciones", "Procesos OS", "Desvíos"])
        ini, fin, kwh = self.MESES[0]
        r = motor.revisar(c, ini, fin, kwh, None)
        self.assertEqual(len(r.detalle), 720)
        esperado = kwh / 1000 * (r.indice_medio - 18.0) * 1.07 * 1.02 * 1.015
        self.assertAlmostEqual(r.importe, esperado)

    def test_comprobacion_encuentra_la_suma_y_la_referencia(self):
        # factura simulada con R+P+D y una referencia de 17 en vez de 18
        verdad = self.contrato(componentes_pfm=["Restricciones", "Procesos OS", "Desvíos"],
                               ref_superior=17.0)
        grupos = [([(a, b, k)], round(motor.revisar(verdad, a, b, k, None).importe, 2))
                  for a, b, k in self.MESES]
        filas = motor.comprobar_componentes(self.contrato(), grupos)
        rpd = [f for f in filas
               if f["Componentes sumados"] == "Restricciones + Procesos OS + Desvíos"]
        self.assertEqual(len(rpd), 1)
        self.assertAlmostEqual(rpd[0]["Ref. implícita €/MWh"], 17.0, places=3)
        self.assertLess(rpd[0]["Variación de la ref. entre líneas"], 0.001)
        self.assertTrue(any(f["Es la del contrato"] for f in filas))

    def test_perdidas_estandar(self):
        self.assertEqual(motor.perd_estandar("6.1TD"), 7.0)
        self.assertEqual(motor.perd_estandar("3.0TD"), 17.0)


class MediasSAHReales(unittest.TestCase):
    """Medias del Total SAH publicadas (dato publico de ESIOS) con una banda 15-20."""

    def test_medias_y_cargo(self):
        c = motor.Contrato(mecanismo="banda", ref_superior=20.0, ref_inferior=15.0)
        for ini, fin, media in [
                (dt.date(2026, 4, 1), dt.date(2026, 4, 30), 25.108917),
                (dt.date(2026, 5, 1), dt.date(2026, 5, 31), 22.967540),
                (dt.date(2026, 6, 1), dt.date(2026, 6, 30), 18.698694)]:
            r = motor.revisar(c, ini, fin, 1000, None)
            self.assertAlmostEqual(r.indice_medio, media, places=6)
            self.assertAlmostEqual(r.importe, max(media - 20.0, 0.0), places=6)


if __name__ == "__main__":
    unittest.main()
