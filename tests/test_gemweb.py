# -*- coding: utf-8 -*-
"""Cliente de Gemweb contra una API simulada (sin red ni credenciales)."""

import datetime as dt
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import curva_consumo
import gemweb

MARZO, OCTUBRE = dt.date(2026, 3, 29), dt.date(2026, 10, 25)


class ApiFalsa(gemweb.ClienteGemweb):
    """Responde como Gemweb: hora de FIN del cuarto y 96 cuartos por dia siempre."""

    def __init__(self):
        super().__init__("usuario", "clave")
        self.peticiones = []

    def _post(self, peticion, timeout=None, **p):
        self.peticiones.append((peticion, p))
        if peticion == "get_inventory":
            if p["search_values"] != "ES0000000000000000XX":
                raise gemweb.GemwebError("No se han encontrado resultados")
            return ET.fromstring("<root><subministrament><id>42</id><cups>ES0000000000000000XX"
                                 "</cups><tarifa>6.1TD</tarifa></subministrament></root>")
        a = dt.datetime.fromisoformat(p["date_from"])
        b = dt.datetime.fromisoformat(p["date_to"]) + dt.timedelta(days=1)
        t, valores = a + dt.timedelta(minutes=15), []
        while t <= b:
            # 1 kWh por cuarto, 2 kWh en la hora 02:00-03:00 para seguirla
            kwh = 2.0 if (t - dt.timedelta(minutes=15)).hour == 2 else 1.0
            valores.append('<value date="%s">%.1f</value>' % (t.strftime("%Y-%m-%d  %H:%M"), kwh))
            t += dt.timedelta(minutes=15)
        return ET.fromstring("<root><subministrament><id>42</id><units>kWh</units><values>%s"
                             "</values></subministrament></root>" % "".join(valores))


class Gemweb(unittest.TestCase):
    def test_dia_normal(self):
        d = dt.date(2026, 4, 1)
        c, sum_ = ApiFalsa().curva("ES0000000000000000XX", d, d)
        self.assertEqual(sum_["tarifa"], "6.1TD")
        self.assertEqual(c.resolucion, "qh")
        self.assertEqual(len(c.valores), 96)
        self.assertEqual(c.valores[(d, 1, 1)], 1.0)
        self.assertEqual(c.valores[(d, 3, 1)], 2.0)
        self.assertEqual(c.total_kwh, 92 + 8)

    def test_marzo_23_horas(self):
        c, _ = ApiFalsa().curva("ES0000000000000000XX", MARZO, MARZO)
        self.assertEqual(max(k[1] for k in c.valores), 23)
        self.assertEqual(len(c.valores), 92)
        self.assertEqual(c.valores[(MARZO, 3, 1)], 3.0)     # 02:00 inexistente + 03:00
        self.assertAlmostEqual(c.total_kwh, 100.0)
        self.assertTrue(any("no existe" in a for a in c.avisos))

    def test_octubre_25_horas(self):
        c, _ = ApiFalsa().curva("ES0000000000000000XX", OCTUBRE, OCTUBRE)
        self.assertEqual(len(c.valores), 100)
        self.assertEqual(c.valores[(OCTUBRE, 3, 1)], 1.0)    # 2 kWh repartidos
        self.assertEqual(c.valores[(OCTUBRE, 4, 1)], 1.0)
        self.assertEqual(c.valores[(OCTUBRE, 5, 1)], 1.0)    # 03:00
        self.assertAlmostEqual(c.total_kwh, 100.0)

    def test_tramos_mensuales_sin_duplicar(self):
        api = ApiFalsa()
        c, _ = api.curva("ES0000000000000000XX", dt.date(2026, 4, 1), dt.date(2026, 6, 30))
        self.assertGreater(len([p for p in api.peticiones if p[0] == "get_metering"]), 2)
        self.assertEqual(len(c.valores), 91 * 96)

    def test_cups_desconocido(self):
        with self.assertRaises(gemweb.GemwebError):
            ApiFalsa().curva("ES9999999999999999ZZ", MARZO, MARZO)


class FicheroCambioHora(unittest.TestCase):
    def test_csv_horario_normalizado_a_24h(self):
        filas = ["Fecha;Hora;kWh"] + ["29/03/2026;%d;1" % h for h in range(1, 25)]
        c = curva_consumo.leer_curva("\n".join(filas).encode(), "c.csv")
        self.assertEqual(len(c.valores), 23)
        self.assertEqual(c.valores[(MARZO, 3)], 2.0)
        self.assertEqual(c.total_kwh, 24)


if __name__ == "__main__":
    unittest.main()
