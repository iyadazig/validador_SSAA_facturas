# -*- coding: utf-8 -*-
"""
Lectores de factura.

- Textos sinteticos con la maqueta de cada comercializadora y datos inventados
  (lo unico que va al repositorio).
- Facturas reales de facturas_ejemplo/ contra facturas_ejemplo/esperado.json:
  ambos estan fuera de git (datos de clientes); si no existen, se omite.
"""

import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import ssaa_motor as motor
from lectores_factura import leer_factura, leer_texto

ENDESA = """
                                                                    CUPS: ES0000000000000000XX0F
                                                                       Modalidad de Contrato: 6.2TD
         Fecha Factura: 03 de septiembre de 2026
          Periodo facturación: 01/08/2026 al 31/08/2026                  CLIENTE DE PRUEBA S.L.
           Factura nº: P00CON000000001
        Término de Energía Variable                                                                    100,00
                                                               P3: 1.000,000 kWh x 0,050000 Eur/kWh = 50,00 Eur
                                                               P6: 2.500,500 kWh x 0,040000 Eur/kWh = 100,02 Eur
         Regularización Servicios Ajuste (SSAA)                3.500,500000 kWh x 0,002000 euros/kWh                                7,00
        Factura emitida en Madrid por Endesa Energía, S.A. Unipersonal. CIF A81948077.
"""

NATURGY = """
              FACTURA Nº                        CUENTA CONTRATO             FORMA DE PAGO
              PI00000000000001               000000000                      Domiciliación
              FECHA EMISIÓN                     CONTRATO electricidad
               05.08.2026                      00000000000000
              FECHA VENCIMIENTO                  CUPS                        DATOS CONTRACTUALES
               20.08.2026                     ES0000000000000000XX0F     Tarifa ATR: 6.1TD Segmento de cargos: 3
               PERIODO                                                   Mercado Libre
               01.07.26 / 31.07.26
             ENERGÍA ACTIVA P1                                           10.000 kWh                            0,100000                1.000,00    Eur
            ENERGÍA ACTIVA P6                                           20.000 kWh                            0,050000                1.000,00    Eur
            REGULARIZACIÓN DE SERVICIOS DE AJUSTE
                                                                           30.000 kWh                         0,00500000                 150,00    Eur
               01.04.2026 - 30.04.2026
            REGULARIZACIÓN DE SERVICIOS DE AJUSTE
                                                                           25.000 kWh                         -0,00100000                 -25,00    Eur
               01.05.2026 - 31.05.2026
            REGULARIZACIÓN DE CARGOS TÉRMINO DE
                                                                                                                                              100,00    Eur
           FONDO DE EFICIENCIA ENERGÉTICA                                                                                            80,00    Eur
                                            A-08431090
"""


class Sinteticas(unittest.TestCase):
    def test_endesa(self):
        f = leer_texto(ENDESA)
        self.assertEqual(f.lector, "Endesa")
        self.assertEqual(f.numero, "P00CON000000001")
        self.assertEqual(f.fecha_emision, dt.date(2026, 9, 3))
        self.assertEqual(f.cups, "ES0000000000000000XX0F")
        self.assertEqual(f.tarifa, "6.2TD")
        self.assertEqual((f.inicio, f.fin), (dt.date(2026, 8, 1), dt.date(2026, 8, 31)))
        self.assertAlmostEqual(f.consumo_kwh, 3500.5)
        self.assertEqual(len(f.lineas_ssaa), 1)
        l = f.lineas_ssaa[0]
        self.assertEqual((l.kwh, l.precio, l.importe), (3500.5, 0.002, 7.0))
        self.assertEqual((l.inicio, l.fin), (f.inicio, f.fin))
        self.assertEqual(f.avisos, [])

    def test_naturgy_varios_meses_y_abono(self):
        f = leer_texto(NATURGY)
        self.assertEqual(f.lector, "Naturgy")
        self.assertEqual(f.numero, "PI00000000000001")
        self.assertEqual(f.fecha_emision, dt.date(2026, 8, 5))
        self.assertEqual(f.tarifa, "6.1TD")
        self.assertEqual((f.inicio, f.fin), (dt.date(2026, 7, 1), dt.date(2026, 7, 31)))
        self.assertEqual(f.consumo_kwh, 30000)
        self.assertEqual(len(f.lineas_ssaa), 2)
        a, m = f.lineas_ssaa
        self.assertEqual((a.inicio, a.fin, a.kwh, a.importe),
                         (dt.date(2026, 4, 1), dt.date(2026, 4, 30), 30000, 150.0))
        self.assertEqual((m.inicio, m.kwh, m.precio, m.importe),
                         (dt.date(2026, 5, 1), 25000, -0.001, -25.0))
        self.assertAlmostEqual(f.importe_ssaa, 125.0)

    def test_aviso_si_no_cuadra(self):
        f = leer_texto(ENDESA.replace("7,00", "9,00"))
        self.assertTrue(any("pero la factura pone" in a for a in f.avisos))


ESPERADO = config.CARPETA_EJEMPLOS / "esperado.json"


@unittest.skipUnless(ESPERADO.exists(), "sin facturas_ejemplo/esperado.json")
class FacturasReales(unittest.TestCase):
    def test_ejemplos(self):
        esperado = json.loads(ESPERADO.read_text(encoding="utf-8"))
        for nombre, e in esperado.items():
            with self.subTest(factura=nombre):
                f = leer_factura((config.CARPETA_EJEMPLOS / nombre).read_bytes())
                for campo in ("lector", "numero", "cups", "tarifa", "consumo_kwh"):
                    self.assertEqual(getattr(f, campo), e[campo], campo)
                for campo in ("fecha_emision", "inicio", "fin"):
                    self.assertEqual(str(getattr(f, campo)), e[campo], campo)
                lineas = [[str(l.inicio), str(l.fin), l.kwh, l.precio, l.importe]
                          for l in f.lineas_ssaa]
                self.assertEqual(lineas, e["lineas"])
                self.assertEqual(f.avisos, [])
                if "contrato" in e:
                    # revision completa con la clausula real (guardada solo en local)
                    c = motor.Contrato.desde_dict(e["contrato"])
                    veredictos = [motor.revisar(c, l.inicio, l.fin, l.kwh, l.importe).veredicto
                                  for l in f.lineas_ssaa]
                    self.assertEqual(veredictos, e["veredictos"])


if __name__ == "__main__":
    unittest.main()
