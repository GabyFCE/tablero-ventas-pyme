#!/usr/bin/env python3
"""Genera data/sample/datos.json: un dataset sintético con la forma del real.

No hay un solo dato de un cliente real: nombres inventados, CUITs inventados,
montos sorteados con semilla fija. Sirve para correr el pipeline entero sin
tener comprobantes.

    python3 scripts/generar_muestra.py
    python3 scripts/generar_muestra.py --semilla 7 --salida /tmp/datos.json

El dataset imita tres rasgos del caso real, porque son los que el pipeline
tiene que poder mostrar:

- dos clientes concentran casi toda la facturación;
- uno de ellos deja de comprar en el último año y la serie cae a la mitad;
- las notas de crédito existen y hay que restarlas.

Los importes son sintéticos: cada comprobante apunta a un ticket en dólares y
se convierte a pesos con un tipo de cambio de referencia por año, así la serie
en dólares de hoy queda estable salvo por la caída final.
"""

import argparse
import csv
import json
import random
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
EMISOR = "20111111112"


def cargar_series():
    """Las mismas series que usa el pipeline: así el ticket en USD de hoy queda estable."""
    ipc, ccl = {}, {}
    for fila in csv.DictReader(open(BASE / "data" / "ipc.csv", encoding="utf-8")):
        ipc[fila["ym"]] = float(fila["ipc"])
    for fila in csv.DictReader(open(BASE / "data" / "ccl.csv", encoding="utf-8")):
        ccl[fila["ym"]] = float(fila["ccl"])
    return ipc, ccl

# (nombre, CUIT inventado, ticket en USD, meses de compra, último año que compra)
CLIENTES = [
    ("CLIENTE ALFA S.A.", "30711111116", 900, list(range(1, 13)), 2026),
    ("CLIENTE BETA S.R.L.", "30711111124", 3000, [4, 6, 12], 2025),
    ("CLIENTE GAMMA S.A.", "30711111132", 250, [5, 11], 2026),
    ("CLIENTE DELTA S.R.L.", "30711111140", 200, [3, 9], 2026),
    ("CLIENTE EPSILON S.A.", "30711111159", 150, [7], 2022),
    ("CLIENTE ZETA S.A.", "30711111167", 120, [10], 2021),
]

ITEMS = [
    "Carcasa de turbina arenada",
    "Carcasa de entrada de gases arenada",
    "Difusor de gases arenado",
    "Base de anclaje arenada",
    "Anillo de tobera arenado",
    "Protección térmica arenada",
    "Carcasa de salida de gases arenada",
    "Brida de acople arenada",
]


def pesos(valor):
    """12345.6 → '12.345,60' (formato de los comprobantes argentinos)."""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--semilla", type=int, default=20261123)
    ap.add_argument("--salida", default=str(BASE / "data" / "sample" / "datos.json"))
    args = ap.parse_args()

    rnd = random.Random(args.semilla)
    ipc, ccl = cargar_series()
    ancla_ipc = ipc[list(ipc)[-1]]
    ancla_ccl = ccl[list(ccl)[-1]]
    registros = []
    nro = 0

    for anio in range(2020, 2027):
        for nombre, cuit, ticket_usd, meses, ultimo_anio in CLIENTES:
            if anio > ultimo_anio:
                continue
            for mes in meses:
                ym = f"{anio}-{mes:02d}"
                if ym < list(ipc)[0] or ym < list(ccl)[0]:
                    continue  # anterior al comienzo de las series
                # Un mes sin publicar usa el último valor de la serie, igual que el pipeline:
                # esos comprobantes quedan en valores nominales y se informan.
                ipc_mes = ipc.get(ym, ipc[list(ipc)[-1]])
                ccl_mes = ccl.get(ym, ccl[list(ccl)[-1]])
                monto_usd = ticket_usd * rnd.uniform(0.85, 1.15)
                if nombre.startswith("CLIENTE BETA") and anio == 2025 and mes == 12:
                    monto_usd *= 2.2  # el último lote grande antes de irse
                # Inversa de la fórmula del pipeline: el ticket queda en USD de hoy.
                total = round(monto_usd * ancla_ccl * ipc_mes / ancla_ipc, 2)
                neto = round(total / 1.21, 2)
                cantidad = rnd.choice([1, 2, 3, 4, 6, 8, 12])
                precio = round(neto / cantidad, 2)
                desc = rnd.choice(ITEMS)
                item = (f"{desc} {cantidad},00 unidades {pesos(precio)} 0,00 "
                        f"{pesos(neto)} 21% {pesos(total)}")
                nro += 1
                dia = rnd.choice([2, 5, 8, 9, 12, 14, 20, 27])
                registros.append({
                    "file": f"{EMISOR}_001_00001_{nro:08d}.pdf",
                    "emisor": EMISOR,
                    "tipo": "FAC",
                    "letra": "A",
                    "fecha": date(anio, mes, dia).strftime("%d/%m/%Y"),
                    "total": total,
                    "neto": neto,
                    "cliente": nombre,
                    "cuit_cli": cuit,
                    "pv": "00001",
                    "nro": f"{nro:08d}",
                    "ref": None,
                    "concepto": item,
                    "items": [item],
                })

    # Dos notas de crédito igual que en el caso real: una por devolución y otra
    # que anula una factura del cliente que después se va.
    for anio, importe in ((2022, 164560.0), (2025, 3097600.0)):
        nro += 1
        registros.append({
            "file": f"{EMISOR}_001_00001_{nro:08d}.pdf",
            "emisor": EMISOR,
            "tipo": "NC",
            "letra": "A",
            "fecha": f"14/{'06' if anio == 2022 else '04'}/{anio}",
            "total": importe,
            "neto": round(importe / 1.21, 2),
            "cliente": "CLIENTE BETA S.R.L.",
            "cuit_cli": "30711111124",
            "pv": "00001",
            "nro": f"{nro:08d}",
            "ref": "00001-00000042",
            "concepto": "Nota de crédito por devolución de material",
            "items": ["Nota de crédito por devolución de material"],
        })

    registros.sort(key=lambda r: (r["fecha"][6:], r["fecha"][3:5], r["fecha"][:2], r["nro"]))
    Path(args.salida).write_text(json.dumps(registros, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(registros)} comprobantes sintéticos → {args.salida}")


if __name__ == "__main__":
    main()
