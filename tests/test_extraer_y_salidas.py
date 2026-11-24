"""Tests de la extracción y de la salida a Excel.

Los de extracción prueban las funciones puras (no necesitan PDFs ni pypdf).
Los de la salida se saltean si openpyxl no está instalado.
"""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))

import extraer  # noqa: E402


class TestEmisor(unittest.TestCase):
    """El CUIT del emisor sale del comprobante, no de una constante."""

    TEXTO = (
        "Fecha de Emisión:\nORIGINAL\nEMPRESA EJEMPLO S.A.\n"
        "CUIT:\n08/01/2026\n20111111112\n30711111116 CLIENTE DE PRUEBA S.A.\n"
        "Punto de Venta: Comp. Nro:00002 00000123\n"
    )

    def test_detecta_el_cuit_solo_en_su_linea(self):
        self.assertEqual(extraer.emisor_de(self.TEXTO), "20111111112")

    def test_no_confunde_emisor_con_receptor(self):
        em = extraer.emisor_de(self.TEXTO)
        self.assertNotEqual(em, "30711111116")

    def test_acepta_cuit_con_guiones(self):
        texto = "EMPRESA EJEMPLO S.A.\n20-11111111-2\n30711111116 CLIENTE S.A."
        self.assertEqual(extraer.emisor_de(texto), "20111111112")

    def test_sin_cuit_devuelve_none(self):
        self.assertIsNone(extraer.emisor_de("texto sin números"))

    def test_importe_con_formato_argentino(self):
        self.assertEqual(extraer.num("1.234.567,89"), 1234567.89)
        self.assertIsNone(extraer.num(None))


class TestSalidas(unittest.TestCase):
    def setUp(self):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl no está instalado")

    def test_libro_cinco_hojas_y_totales_coherentes(self):
        import importlib
        salidas = importlib.import_module("salidas")

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "ventas.csv"
            meta_path = Path(tmp) / "ventas.csv.meta.json"
            xlsx_path = Path(tmp) / "ventas.xlsx"

            # genera el CSV normalizado con el núcleo
            import json
            import normalizar
            datos = json.loads((BASE / "data" / "sample" / "datos.json").read_text(encoding="utf-8"))
            ipc = normalizar.cargar_serie(BASE / "data" / "ipc.csv", "ipc")
            ccl = normalizar.cargar_serie(BASE / "data" / "ccl.csv", "ccl")
            filas, info = normalizar.normalizar(datos, ipc, ccl)
            digest = normalizar.escribir_csv(filas, csv_path, respaldo=False)
            meta_path.write_text(json.dumps({**info, "sha256": digest}), encoding="utf-8")

            wb = salidas.construir(salidas.leer_csv(csv_path), json.loads(meta_path.read_text()))
            wb.save(xlsx_path)

            from openpyxl import load_workbook
            libro = load_workbook(xlsx_path)
            self.assertEqual(libro.sheetnames,
                             ["Comprobantes", "Resumen anual", "Mensual", "Clientes", "Metodología"])

            hoja = libro["Comprobantes"]
            self.assertEqual(hoja.max_row - 1, len(filas))

            resumen = libro["Resumen anual"]
            total_libro = sum(r[5] for r in resumen.iter_rows(min_row=2, values_only=True))
            self.assertAlmostEqual(float(total_libro), float(sum(f["usd_hoy"] for f in filas)), places=2)


if __name__ == "__main__":
    unittest.main()
