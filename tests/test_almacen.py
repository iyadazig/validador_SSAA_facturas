# -*- coding: utf-8 -*-
"""Base de datos compartida (usuarios, fichas, revisiones) en una carpeta temporal."""

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import almacen
import config


class Almacen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        carpeta = Path(self.tmp.name)
        self.json = carpeta / "contratos_ssaa.json"
        self.json.write_text(json.dumps({"ES0000000000000000XX": {"cups": "ES0000000000000000XX",
                                                                 "techo": 18.0}}), "utf-8")
        self.p = [mock.patch.object(config, "CARPETA_DATOS", carpeta),
                  mock.patch.object(config, "FICHERO_CONTRATOS", self.json)]
        for p in self.p:
            p.start()
        almacen._iniciado.clear()

    def tearDown(self):
        for p in self.p:
            p.stop()
        almacen._iniciado.clear()
        self.tmp.cleanup()

    def test_importa_fichas_del_json(self):
        self.assertEqual(almacen.cargar_contratos()["ES0000000000000000XX"]["techo"], 18.0)

    def test_usuarios_y_contrasena(self):
        self.assertFalse(almacen.hay_usuarios())
        with self.assertRaises(ValueError):
            almacen.crear_usuario("ana", "Ana", "corta1")           # menos de 10
        almacen.crear_usuario("Ana", "Ana López", "clave-segura-1", admin=True)
        self.assertTrue(almacen.hay_usuarios())
        u = almacen.comprobar("ANA ", "clave-segura-1")
        self.assertEqual((u["usuario"], u["admin"]), ("ana", 1))
        with self.assertRaises(ValueError):
            almacen.comprobar("ana", "otra-clave-123")
        with self.assertRaises(ValueError):
            almacen.crear_usuario("ana", "Repetida", "clave-segura-2")

    def test_bloqueo_tras_cinco_fallos(self):
        almacen.crear_usuario("luis", "Luis", "clave-segura-1")
        for _ in range(5):
            with self.assertRaises(ValueError):
                almacen.comprobar("luis", "mala-clave-000")
        with self.assertRaises(ValueError) as e:
            almacen.comprobar("luis", "clave-segura-1")      # bloqueado aunque sea buena
        self.assertIn("Demasiados intentos", str(e.exception))

    def test_siempre_queda_un_admin(self):
        almacen.crear_usuario("admin", "Admin", "clave-segura-1", admin=True)
        with self.assertRaises(ValueError):
            almacen.actualizar_usuario("admin", activo=False)
        self.assertTrue(almacen.listar_usuarios()[0]["activo"])

    def test_historial_de_fichas(self):
        self.assertTrue(almacen.guardar_contrato("ES1", {"techo": 17.0}, "ana"))
        self.assertFalse(almacen.guardar_contrato("ES1", {"techo": 17.0}, "ana"))  # sin cambios
        self.assertTrue(almacen.guardar_contrato("ES1", {"techo": 17.5}, "luis"))
        h = almacen.historial_contrato("ES1")
        self.assertEqual([x["accion"] for x in h], ["modificada", "creada"])
        self.assertEqual(almacen.info_contratos()["ES1"][1], "luis")

    def test_revisiones(self):
        rid = almacen.guardar_revision(
            "ana", {"cups": "ES1", "factura": "F1"},
            [{"Facturado €": 10.0, "Recalculado €": 8.0, "Veredicto": "FACTURADO DE MÁS"}],
            b"xlsx")
        r = almacen.listar_revisiones()[0]
        self.assertEqual((r["id"], r["diferencia"], r["veredicto"]), (rid, 2.0, "FACTURADO DE MÁS"))
        self.assertEqual(almacen.informe_revision(rid)[0], b"xlsx")

    def test_escrituras_simultaneas(self):
        errores = []

        def guardar(i):
            try:
                for j in range(10):
                    almacen.guardar_contrato("ES%d" % i, {"techo": j}, "u%d" % i)
            except Exception as e:      # pragma: no cover
                errores.append(e)
        hilos = [threading.Thread(target=guardar, args=(i,)) for i in range(6)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(errores, [])
        self.assertEqual(len(almacen.cargar_contratos()), 7)     # 6 + la importada


if __name__ == "__main__":
    unittest.main()
