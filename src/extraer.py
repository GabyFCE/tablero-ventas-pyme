#!/usr/bin/env python3
"""Extrae comprobantes de PDFs al formato de registro del pipeline.

Transcribe, no interpreta: no firma notas de crédito, no convierte moneda, no
redondea importes. Todo eso pasa después, en normalizar.py.

El emisor se lee del propio comprobante (en el PDF de AFIP el bloque del emisor
trae su CUIT solo en su línea; el del receptor viene seguido del nombre).
--emisor lo fuerza si un comprobante raro no lo trae suelto.

    python3 src/extraer.py --pdfs comprobantes/ --salida datos.json
    python3 src/extraer.py --pdfs comprobantes/ --salida - | head -c 200

Requiere pypdf. Si no está instalado, el resto del pipeline se puede correr
igual partiendo de un datos.json ya extraído (data/sample/datos.json).
"""

import argparse
import json
import re
import sys
from pathlib import Path

CUIT = r"\d{2}-?\d{8}-?\d"
# Códigos de comprobante de AFIP → letra.
COD = {"01": "A", "06": "B", "11": "C", "03": "A", "08": "B", "13": "C",
       "02": "A", "07": "B", "12": "C"}


def num(s):
    """Importe con formato argentino (`1.234.567,89`) → float. None si no parsea."""
    if not s:
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def solo_digitos(s):
    """CUIT con o sin guiones → once dígitos, que es como se compara."""
    return re.sub(r"\D", "", s)


def emisor_de(texto):
    """CUIT del emisor según el texto del comprobante."""
    for m in re.finditer(r"(?m)^\s*(" + CUIT + r")\s*$", texto):
        return solo_digitos(m.group(1))
    m = re.search(r"CUIT:?\s*(" + CUIT + r")", texto)
    if m:
        return solo_digitos(m.group(1))
    m = re.search(CUIT, texto)
    return solo_digitos(m.group(0)) if m else None


def parsear(ruta, forzar_emisor=None):
    """Un PDF → un registro crudo. Devuelve lo que dice el papel, sin interpretar."""
    # Import local: el módulo se puede importar (y testear) sin pypdf instalado.
    from pypdf import PdfReader  # import local: el resto del módulo no lo necesita

    texto = "\n".join(p.extract_text() or "" for p in PdfReader(str(ruta)).pages)
    em = forzar_emisor or emisor_de(texto)
    tipo = "NC" if re.search(r"NOTA DE CR", texto, re.I) else (
        "ND" if re.search(r"NOTA DE D", texto, re.I) else "FAC")
    cod = re.search(r"COD\.\s*(\d{2})", texto)
    total = re.search(r"Importe Total:\s*\$\s*([\d.,]+)", texto)
    # El comprobante trae tres fechas juntas (emisión, vencimiento, período); la
    # que aparece suelta y sola puede ser cualquiera. Se prefieren las tres.
    tres_fechas = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})", texto)
    suelta = re.search(r"\d{2}/\d{2}/\d{4}", texto)
    fecha = tres_fechas.group(1) if tres_fechas else (suelta.group(0) if suelta else None)
    receptor = re.search(re.escape(em) + r"\s+(" + CUIT + r")\s+([^\n]+)", texto) if em else None
    pv = re.search(r"Punto de Venta:\s*Comp\. Nro:\s*(\d+)\s+(\d+)", texto)
    neto = re.search(r"Importe Neto Gravado:\s*\$\s*([\d.,]+)", texto)
    ref = re.search(r"Fac\.\s*[ABC]:\s*(\d+)-(\d+)", texto)

    lineas = texto.split("\n")

    def descripcion(i):
        """La descripción del ítem suele estar arriba, a veces cortada en dos renglones."""
        partes = []
        j = i - 1
        while j >= 0 and len(partes) < 2:
            s = lineas[j].strip()
            if (not s or s.startswith("Código Producto") or s.startswith("Descripción")
                    or re.match(CUIT + r"$", s)):
                break
            partes.insert(0, s)
            j -= 1
        return " ".join(partes)

    items = []
    for i, linea in enumerate(lineas):
        s = re.sub(r"\s+", " ", linea).strip()
        if not re.search(r"\d+,\d{2}\s+(unidades|[A-Za-z])", s) or "$" in s:
            continue
        if re.match(r"^\d+,\d{2}\s", s):  # arranca con la cantidad
            arriba = descripcion(i)
            if arriba:
                s = (arriba + " " + s).strip()
        items.append(s)
    items = list(dict.fromkeys(x[:120] for x in items))

    return {
        "file": ruta.name,
        "emisor": em,
        "tipo": tipo,
        "letra": COD.get(cod.group(1)) if cod else None,
        "fecha": fecha,
        "total": num(total.group(1)) if total else None,
        "neto": num(neto.group(1)) if neto else None,
        "cliente": receptor.group(2).strip() if receptor else None,
        "cuit_cli": solo_digitos(receptor.group(1)) if receptor else None,
        "pv": pv.group(1) if pv else None,
        "nro": pv.group(2) if pv else None,
        "ref": (ref.group(1) + "-" + ref.group(2)) if ref else None,
        "concepto": " / ".join(items)[:400] if items else None,
        "items": items,
    }


def main():
    base = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdfs", nargs="+", default=[str(base / "comprobantes")],
                    help="carpetas o archivos PDF")
    ap.add_argument("--salida", default=str(base / "datos.json"),
                    help="ruta del JSON, o - para stdout")
    ap.add_argument("--emisor", help="CUIT del emisor a forzar")
    ap.add_argument("--estricto", action="store_true",
                    help="exit 3 si algún registro queda sin cliente o sin total")
    args = ap.parse_args()

    archivos = []
    for p in args.pdfs:
        ruta = Path(p)
        if ruta.is_dir():
            archivos += sorted(ruta.glob("*.pdf"))
        elif ruta.exists():
            archivos.append(ruta)
        else:
            print(f"error: no existe {p}", file=sys.stderr)
            return 2
    if not archivos:
        print("error: no hay PDFs", file=sys.stderr)
        return 2

    registros = sorted((parsear(f, args.emisor) for f in archivos), key=lambda r: r["file"])
    if args.salida == "-":
        json.dump(registros, sys.stdout, ensure_ascii=False)
        return 0

    Path(args.salida).write_text(json.dumps(registros, ensure_ascii=False, indent=1), encoding="utf-8")
    incompletos = [r["file"] for r in registros if not r["cliente"] or r["total"] is None]
    print(json.dumps({
        "archivos": len(registros),
        "emisores": sorted({r["emisor"] for r in registros}),
        "tipos": {t: sum(1 for r in registros if r["tipo"] == t) for t in ("FAC", "NC", "ND")},
        "items": sum(len(r["items"]) for r in registros),
        "incompletos": incompletos,
        "salida": args.salida,
    }), file=sys.stderr)
    return 3 if incompletos and args.estricto else 0


if __name__ == "__main__":
    sys.exit(main())
