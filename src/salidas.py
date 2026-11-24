#!/usr/bin/env python3
"""Arma un libro de Excel a partir del CSV normalizado.

Cinco hojas: Comprobantes, Resumen anual, Mensual, Clientes y Metodología.
Los gráficos son nativos de Excel (no imágenes), así que se pueden tocar.

    python3 src/salidas.py
    python3 src/salidas.py --csv out/ventas_normalizadas.csv --xlsx /tmp/ventas.xlsx

Requiere openpyxl.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

BASE = Path(__file__).resolve().parent.parent
AZUL = PatternFill("solid", fgColor="2F5597")
CABECERA = Font(bold=True, color="FFFFFF")
ROJO = Font(color="C00000")
PESOS = '"$" #,##0'
USD = '"US$" #,##0'
PCT = "0.0%"


def leer_csv(ruta):
    with open(ruta, newline="", encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    for f in filas:
        for k in ("total", "ccl", "pesos_hoy", "usd_epoca", "usd_hoy"):
            f[k] = float(f[k])
    filas.sort(key=lambda f: (f["ym"], f["nro"]))
    return filas


def encabezado(ws, columnas, anchos):
    ws.append(columnas)
    for celda, ancho in zip(ws[1], anchos):
        celda.font = CABECERA
        celda.fill = AZUL
        celda.alignment = Alignment(horizontal="center")
    for i, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
    ws.freeze_panes = "A2"


def construir(filas, meta):
    wb = Workbook()

    ws = wb.active
    ws.title = "Comprobantes"
    encabezado(ws, ["Fecha", "Año-Mes", "Tipo", "Letra", "Nro", "Cliente", "CUIT",
                    "Concepto", "Total nominal", "CCL mes", "$ de hoy", "USD época", "USD hoy"],
               [11, 9, 7, 6, 10, 34, 13, 46, 14, 10, 14, 12, 12])
    for f in filas:
        ws.append([f["fecha"], f["ym"], f["tipo"], f["letra"], f["nro"], f["cliente"],
                   f["cuit_cli"], f["concepto"], f["total"], f["ccl"], f["pesos_hoy"],
                   f["usd_epoca"], f["usd_hoy"]])
        if f["tipo"] == "NC":
            for celda in ws[ws.max_row]:
                celda.font = ROJO
    for r in range(2, ws.max_row + 1):
        for col in (9, 11):
            ws.cell(row=r, column=col).number_format = PESOS
        for col in (10, 12, 13):
            ws.cell(row=r, column=col).number_format = "#,##0.00"

    ws = wb.create_sheet("Resumen anual")
    encabezado(ws, ["Año", "Comprobantes", "Neto nominal", "$ de hoy", "USD época", "USD de hoy"],
               [8, 14, 16, 16, 14, 14])
    anual = defaultdict(lambda: defaultdict(float))
    for f in filas:
        a = anual[f["y"]]
        a["n"] += 1
        for k in ("total", "pesos_hoy", "usd_epoca", "usd_hoy"):
            a[k] += f[k]
    for y in sorted(anual):
        a = anual[y]
        ws.append([y, int(a["n"]), a["total"], a["pesos_hoy"], a["usd_epoca"], a["usd_hoy"]])
    for r in range(2, ws.max_row + 1):
        ws.cell(row=r, column=3).number_format = PESOS
        ws.cell(row=r, column=4).number_format = PESOS
        for col in (5, 6):
            ws.cell(row=r, column=col).number_format = USD
    g = BarChart()
    g.title = "USD de hoy por año"
    g.y_axis.title = "USD"
    g.add_data(Reference(ws, min_col=6, min_row=1, max_row=ws.max_row), titles_from_data=True)
    g.set_categories(Reference(ws, min_col=1, min_row=2, max_row=ws.max_row))
    g.height, g.width = 8, 16
    ws.add_chart(g, "H2")

    ws = wb.create_sheet("Mensual")
    encabezado(ws, ["Mes", "Comprobantes", "Neto nominal", "$ de hoy", "USD de hoy"],
               [10, 14, 16, 16, 14])
    mes = defaultdict(lambda: defaultdict(float))
    for f in filas:
        m = mes[f["ym"]]
        m["n"] += 1
        for k in ("total", "pesos_hoy", "usd_hoy"):
            m[k] += f[k]
    for ym in sorted(mes):
        m = mes[ym]
        ws.append([ym, int(m["n"]), m["total"], m["pesos_hoy"], m["usd_hoy"]])
    for r in range(2, ws.max_row + 1):
        ws.cell(row=r, column=3).number_format = PESOS
        ws.cell(row=r, column=4).number_format = PESOS
        ws.cell(row=r, column=5).number_format = USD
    g = LineChart()
    g.title = "USD de hoy por mes"
    g.y_axis.title = "USD"
    g.add_data(Reference(ws, min_col=5, min_row=1, max_row=ws.max_row), titles_from_data=True)
    g.set_categories(Reference(ws, min_col=1, min_row=2, max_row=ws.max_row))
    g.height, g.width = 9, 20
    ws.add_chart(g, "G2")

    ws = wb.create_sheet("Clientes")
    encabezado(ws, ["Cliente", "Comprobantes", "USD de hoy", "% del total", "2025", "2026", "Última"],
               [36, 14, 14, 11, 12, 12, 11])
    cli = defaultdict(lambda: {"n": 0, "usd": 0.0, "por_anio": defaultdict(float), "ultima": None})
    for f in filas:
        c = cli[f["cliente"]]
        c["n"] += 1
        c["usd"] += f["usd_hoy"]
        c["por_anio"][f["y"]] += f["usd_hoy"]
        fecha = datetime.strptime(f["fecha"], "%d/%m/%Y")
        if c["ultima"] is None or fecha > c["ultima"]:
            c["ultima"] = fecha
    total = sum(c["usd"] for c in cli.values()) or 1
    for nombre in sorted(cli, key=lambda n: -cli[n]["usd"]):
        c = cli[nombre]
        ws.append([nombre, c["n"], c["usd"], c["usd"] / total,
                   c["por_anio"].get("2025", 0.0), c["por_anio"].get("2026", 0.0),
                   c["ultima"].strftime("%d/%m/%Y") if c["ultima"] else ""])
    for r in range(2, ws.max_row + 1):
        ws.cell(row=r, column=3).number_format = USD
        ws.cell(row=r, column=4).number_format = PCT
        for col in (5, 6):
            ws.cell(row=r, column=col).number_format = USD

    ws = wb.create_sheet("Metodología")
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 110
    filas_meta = [
        ("Fuentes", ""),
        ("IPC nacional (INDEC)", f"Serie 148.3_INIVELNAL_DICI_M_26 vía datos.gob.ar. "
                                 f"Deflactor: {meta['ipc_ancla']['ym']} = {meta['ipc_ancla']['valor']}."),
        ("CCL", f"Promedio mensual del contado con liquidación. "
                f"Anclaje: {meta['ccl_ancla']['origen']} = {meta['ccl_ancla']['valor']}."),
        ("", ""),
        ("Cálculos", ""),
        ("$ de hoy", "Total nominal × (IPC del deflactor / IPC del mes del comprobante)."),
        ("USD época", "Total nominal / CCL promedio del mes del comprobante."),
        ("USD de hoy", "($ de hoy) / CCL de anclaje."),
        ("", ""),
        ("Advertencias", ""),
        ("Rezago del IPC", "El deflactor llega hasta el último mes publicado; los meses "
                           "posteriores quedan en valores nominales: "
                           f"{', '.join(meta['meses_sin_serie']) or 'ninguno'}."),
        ("CCL promedio", "Se usa el promedio del mes, no la cotización del día de cada comprobante."),
        ("Notas de crédito", "Entran en negativo antes de cualquier cálculo."),
        ("Generación", f"{meta['filas']} comprobantes. SHA-256 del CSV: {meta['sha256'][:16]}…"),
    ]
    for a, b in filas_meta:
        ws.append([a, b])
        if not b:
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
        ws.cell(row=ws.max_row, column=2).alignment = Alignment(wrap_text=True, vertical="top")

    return wb


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", default=str(BASE / "out" / "ventas_normalizadas.csv"))
    ap.add_argument("--meta", default=None, help="default: <csv>.meta.json")
    ap.add_argument("--xlsx", default=str(BASE / "out" / "ventas.xlsx"))
    args = ap.parse_args()

    meta_path = Path(args.meta or str(args.csv) + ".meta.json")
    if not meta_path.exists():
        print(f"error: falta {meta_path} (lo escribe normalizar.py)", file=sys.stderr)
        return 2

    filas = leer_csv(args.csv)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    wb = construir(filas, meta)
    Path(args.xlsx).parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.xlsx)
    print(json.dumps({"ok": True, "xlsx": args.xlsx, "hojas": wb.sheetnames,
                      "comprobantes": len(filas)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
