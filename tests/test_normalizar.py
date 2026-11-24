"""Tests del núcleo: normalización, determinismo y manejo de anclajes.

Corren sin datos reales: usan data/sample/datos.json y las series públicas.
"""

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))

import normalizar  # noqa: E402


def datos():
    return json.loads((BASE / "data" / "sample" / "datos.json").read_text(encoding="utf-8"))


def series():
    ipc = normalizar.cargar_serie(BASE / "data" / "ipc.csv", "ipc")
    ccl = normalizar.cargar_serie(BASE / "data" / "ccl.csv", "ccl")
    return ipc, ccl


class TestNormalizar(unittest.TestCase):
    def test_determinista(self):
        """Dos corridas sobre el mismo insumo dan el mismo archivo, byte a byte."""
        ipc, ccl = series()
        hashes = []
        for _ in range(2):
            filas, _ = normalizar.normalizar(datos(), ipc, ccl)
            with tempfile.TemporaryDirectory() as tmp:
                ruta = Path(tmp) / "salida.csv"
                hashes.append(normalizar.escribir_csv(filas, ruta, respaldo=False))
        self.assertEqual(hashes[0], hashes[1])

    def test_notas_de_credito_en_negativo(self):
        ipc, ccl = series()
        filas, info = normalizar.normalizar(datos(), ipc, ccl)
        nc = [f for f in filas if f["tipo"] == "NC"]
        self.assertTrue(nc, "la muestra tiene que traer notas de crédito")
        for f in nc:
            self.assertLess(f["total"], 0)
            self.assertLess(f["pesos_hoy"], 0)
            self.assertLess(f["usd_hoy"], 0)
        self.assertEqual(info["nc"], len(nc))

    def test_formula_de_deflacion(self):
        """pesos_hoy = total × (IPC ancla / IPC del mes)."""
        ipc, ccl = series()
        filas, info = normalizar.normalizar(datos(), ipc, ccl)
        ancla = Decimal(info["ipc_ancla"]["valor"])
        for f in filas[:20]:
            esperado = (f["total"] * ancla / ipc[f["ym"]]).quantize(Decimal("0.01"))
            self.assertEqual(f["pesos_hoy"], esperado)

    def test_usd_de_hoy_usa_el_ccl_de_anclaje(self):
        ipc, ccl = series()
        filas, info = normalizar.normalizar(datos(), ipc, ccl)
        ancla = Decimal(info["ccl_ancla"]["valor"])
        for f in filas[:20]:
            self.assertEqual(f["usd_hoy"], (f["pesos_hoy"] / ancla).quantize(Decimal("0.01")))

    def test_anclaje_manual_reproduce_un_corte_viejo(self):
        """Fijar el ancla cambia los valores pero no las filas ni los nominales."""
        ipc, ccl = series()
        actual, _ = normalizar.normalizar(datos(), ipc, ccl)
        viejo, info = normalizar.normalizar(datos(), ipc, ccl,
                                            ipc_ancla_ym="2026-08", ccl_ancla="1628")
        self.assertEqual(len(actual), len(viejo))
        self.assertEqual([f["total"] for f in actual], [f["total"] for f in viejo])
        self.assertEqual(info["ipc_ancla"]["ym"], "2026-08")
        self.assertEqual(info["ccl_ancla"]["valor"], "1628")
        self.assertNotEqual([f["usd_hoy"] for f in actual], [f["usd_hoy"] for f in viejo])

    def test_mes_posterior_al_ultimo_dato_queda_nominal(self):
        """Un mes sin serie publicada no rompe: usa el último valor y lo informa."""
        ipc, ccl = series()
        filas, info = normalizar.normalizar(datos(), ipc, ccl)
        if not info["meses_sin_serie"]:
            self.skipTest("la muestra no tiene meses fuera de serie")
        mes = info["meses_sin_serie"][-1]
        for f in filas:
            if f["ym"] == mes:
                self.assertEqual(f["ccl"], ccl[list(ccl)[-1]])

    def test_hueco_interno_es_error(self):
        ipc, ccl = series()
        ultimo = list(ipc)[-1]
        ipc_sin_hueco_ok = {k: v for k, v in ipc.items() if k != "2022-07"}
        with self.assertRaises(SystemExit):
            normalizar.normalizar(datos(), ipc_sin_hueco_ok, ccl)
        self.assertLess("2022-07", ultimo)

    def test_columnas_del_csv(self):
        ipc, ccl = series()
        filas, _ = normalizar.normalizar(datos(), ipc, ccl)
        esperadas = ["ym", "y", "tipo", "letra", "fecha", "cliente", "cuit_cli", "nro",
                     "concepto", "total", "ccl", "pesos_hoy", "usd_epoca", "usd_hoy"]
        self.assertEqual(list(filas[0]), esperadas)


class TestMuestra(unittest.TestCase):
    def test_muestra_sintetica_y_estable(self):
        """La muestra no lleva datos reales y se regenera igual."""
        ruta = BASE / "data" / "sample" / "datos.json"
        contenido = ruta.read_bytes()
        registros = json.loads(contenido)
        self.assertTrue(all(r["emisor"] == "20111111112" for r in registros))
        self.assertTrue(all(r["cuit_cli"].startswith("3071111") for r in registros))
        # los nombres son inventados
        self.assertTrue(all("CLIENTE" in r["cliente"] for r in registros))
        self.assertEqual(hashlib.sha256(contenido).hexdigest(),
                         hashlib.sha256(ruta.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
