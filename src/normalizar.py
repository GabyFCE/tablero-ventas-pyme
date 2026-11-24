#!/usr/bin/env python3
"""Convierte registros crudos en una serie de ventas comparable en el tiempo.

Toma el JSON que sale de extraer.py (o el dataset sintético) y dos series
mensuales versionadas en data/: IPC y CCL. Escribe un CSV con el nominal, el
valor en pesos de hoy y en dólares de la época y de hoy.

Determinista y sin red: mismos datos + mismas tablas + mismos anclajes = mismo
archivo. Las series se actualizan aparte y se versionan en el repo.

    python3 src/normalizar.py
    python3 src/normalizar.py --ipc-anchor 2026-08 --ccl-anchor 1628   # reproducir un corte viejo

Reglas:
    pesos_hoy = total * (ipc_ancla / ipc_mes)
    usd_epoca = total / ccl_mes
    usd_hoy   = pesos_hoy / ccl_ancla
    Las notas de crédito entran en negativo.
"""

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CENT = Decimal("0.01")


def cargar_serie(ruta, columna):
    """Lee una serie mensual (`ym`, valor) y la devuelve ordenada por mes."""
    serie = {}
    with open(ruta, newline="", encoding="utf-8") as fh:
        for fila in csv.DictReader(fh):
            serie[fila["ym"]] = Decimal(fila[columna])
    if not serie:
        raise SystemExit(f"error: {ruta} está vacío")
    return dict(sorted(serie.items()))


def ym_de(fecha):
    """`dd/mm/aaaa` → `aaaa-mm`. El día no se usa: la serie es mensual."""
    dia, mes, anio = fecha.split("/")
    return f"{anio}-{mes}"


def redondear(valor):
    """Redondeo comercial (0,005 sube), no el de Python por defecto.

    `round()` usa banca (redondea al par), así que dos centavos pueden caer
    para lados distintos según el dígito anterior y el total no cierra.
    """
    return valor.quantize(CENT, rounding=ROUND_HALF_UP)


def normalizar(datos, ipc, ccl, ipc_ancla_ym=None, ccl_ancla=None):
    """Devuelve (filas, informacion). Sin efectos de lado: se puede testear."""
    ipc_ym = ipc_ancla_ym or list(ipc)[-1]
    if ipc_ym not in ipc:
        raise SystemExit(f"error: no hay IPC para {ipc_ym}")
    ancla_ipc = ipc[ipc_ym]

    if ccl_ancla:
        ancla_ccl = Decimal(str(ccl_ancla))
        origen_ccl = f"fijado a mano: {ccl_ancla}"
    else:
        ultimo_ccl_ym = list(ccl)[-1]
        ancla_ccl = ccl[ultimo_ccl_ym]
        origen_ccl = f"promedio de {ultimo_ccl_ym}"

    ultimo_ipc, ultimo_ccl = list(ipc)[-1], list(ccl)[-1]
    sin_serie = set()
    for r in datos:
        ym = ym_de(r["fecha"])
        # Hueco en el medio de la serie: error. Mes posterior al último dato:
        # se usa el último valor (queda nominal) y se informa.
        if ym not in ipc and ym < ultimo_ipc:
            raise SystemExit(f"error: hueco de IPC en {ym}")
        if ym not in ccl and ym < ultimo_ccl:
            raise SystemExit(f"error: hueco de CCL en {ym}")
        if ym not in ipc or ym not in ccl:
            sin_serie.add(ym)

    def ipc_de(ym):
        return ipc.get(ym, ipc[ultimo_ipc])

    def ccl_de(ym):
        return ccl.get(ym, ccl[ultimo_ccl])

    filas = []
    for r in datos:
        ym = ym_de(r["fecha"])
        total = Decimal(str(r["total"]))
        # El signo se aplica antes de deflactar y de dividir por el CCL: si se
        # restara al final, los totales quedarían bien pero cada fila mal.
        if r["tipo"] == "NC":
            total = -total
        pesos_hoy = total * ancla_ipc / ipc_de(ym)
        filas.append({
            "ym": ym,
            "y": ym[:4],
            "tipo": r["tipo"],
            "letra": r.get("letra") or "",
            "fecha": r["fecha"],
            "cliente": r.get("cliente") or "",
            "cuit_cli": r.get("cuit_cli") or "",
            "nro": r.get("nro") or "",
            "concepto": r.get("concepto") or "",
            "total": redondear(total),
            "ccl": ccl_de(ym),
            "pesos_hoy": redondear(pesos_hoy),
            "usd_epoca": redondear(total / ccl_de(ym)),
            "usd_hoy": redondear(pesos_hoy / ancla_ccl),
        })
    # Orden explícito por mes y número: sin esto el CSV cambia de orden entre
    # corridas y deja de ser reproducible byte a byte.
    filas.sort(key=lambda f: (f["ym"], f["nro"]))

    info = {
        "filas": len(filas),
        "nc": sum(1 for f in filas if f["tipo"] == "NC"),
        "ipc_ancla": {"ym": ipc_ym, "valor": str(ancla_ipc)},
        "ccl_ancla": {"valor": str(ancla_ccl), "origen": origen_ccl},
        "meses_sin_serie": sorted(sin_serie),
    }
    return filas, info


def escribir_csv(filas, salida, respaldo=True):
    """Escribe el CSV y devuelve su SHA-256. El respaldo va antes de pisar el archivo."""
    salida = Path(salida)
    if salida.exists() and respaldo:
        sello = datetime.now().strftime("%Y%m%dT%H%M%S")
        shutil.copy2(salida, salida.with_name(salida.name + f".bak-{sello}"))
    columnas = list(filas[0])
    with open(salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)
    return hashlib.sha256(salida.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--datos", default=str(BASE / "data" / "sample" / "datos.json"))
    ap.add_argument("--ipc", default=str(BASE / "data" / "ipc.csv"))
    ap.add_argument("--ccl", default=str(BASE / "data" / "ccl.csv"))
    ap.add_argument("--salida", default=str(BASE / "out" / "ventas_normalizadas.csv"))
    ap.add_argument("--ipc-anchor", help="ym del IPC de referencia (default: último de la tabla)")
    ap.add_argument("--ccl-anchor", help="CCL de referencia (default: promedio del último mes)")
    ap.add_argument("--sin-backup", action="store_true")
    args = ap.parse_args()

    datos = json.loads(Path(args.datos).read_text(encoding="utf-8"))
    ipc = cargar_serie(args.ipc, "ipc")
    ccl = cargar_serie(args.ccl, "ccl")
    filas, info = normalizar(datos, ipc, ccl, args.ipc_anchor, args.ccl_anchor)

    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    digest = escribir_csv(filas, args.salida, respaldo=not args.sin_backup)

    resumen = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        **info,
        "neto_nominal": str(redondear(sum(f["total"] for f in filas))),
        "pesos_hoy": str(redondear(sum(f["pesos_hoy"] for f in filas))),
        "usd_hoy": str(redondear(sum(f["usd_hoy"] for f in filas))),
        "fuentes": {"ipc": str(args.ipc), "ccl": str(args.ccl), "datos": str(args.datos)},
        "sha256": digest,
    }
    Path(str(args.salida) + ".meta.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
