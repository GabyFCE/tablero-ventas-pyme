# tablero-ventas-pyme

Toma comprobantes de AFIP en PDF y devuelve un CSV con una fila por comprobante:
importe nominal, importe en pesos del mes de referencia y en dólares.

```
PDF ──extraer.py──▶ datos.json ──normalizar.py──▶ ventas.csv ──salidas.py──▶ ventas.xlsx
                                        ▲
                          data/ipc.csv ─┤
                          data/ccl.csv ─┘
```

## Requisitos

Python 3.9 o superior. `pypdf` para leer PDFs, `openpyxl` para el libro de Excel. El paso de normalización usa solo la biblioteca estándar.

```bash
pip install pypdf openpyxl
```

## Uso

```bash
# comprobantes → registros crudos
python3 src/extraer.py --pdfs comprobantes/ --salida datos.json

# registros + series → CSV
python3 src/normalizar.py --datos datos.json --salida out/ventas.csv

# CSV → libro de Excel
python3 src/salidas.py --csv out/ventas.csv --xlsx out/ventas.xlsx
```

El repo no incluye comprobantes. Para correr el pipeline completo hay un dataset sintético:

```bash
python3 scripts/generar_muestra.py     # 137 registros inventados, semilla fija
python3 src/normalizar.py              # lee data/sample/datos.json
python3 src/salidas.py
python3 -m unittest discover -s tests
```

## Cálculo

Las series son niveles mensuales. Con `IPC` y `CCL` del mes de cada comprobante:

```
pesos_hoy = total × (IPC_ancla / IPC_mes)
usd_epoca = total / CCL_mes
usd_hoy   = pesos_hoy / CCL_ancla
```

El ancla por defecto es el último mes publicado de cada serie. También se puede fijar:

```bash
python3 src/normalizar.py --ipc-anchor 2026-10 --ccl-anchor 1693.29
```

Cambiar el ancla modifica los importes en pesos y dólares de hoy, no las filas ni los nominales. El ancla usada queda en `out/ventas.csv.meta.json`, junto al SHA-256 del CSV.

Las notas de crédito entran en negativo antes de cualquier cálculo.

Un mes posterior al último dato publicado usa el último valor de la serie y queda registrado en `meses_sin_serie`. Un mes faltante en el medio de la serie corta la ejecución con error.

## Formato de entrada

`datos.json`, un registro por comprobante:

```json
{
  "file": "20111111112_001_00001_00000123.pdf",
  "emisor": "20111111112",
  "tipo": "FAC",
  "letra": "A",
  "fecha": "08/01/2026",
  "total": 1234567.89,
  "neto": 1020303.21,
  "cliente": "CLIENTE ALFA S.A.",
  "cuit_cli": "30711111116",
  "pv": "00001",
  "nro": "00000123",
  "ref": null,
  "concepto": "Carcasa de turbina arenada 2,00 unidades ...",
  "items": ["Carcasa de turbina arenada 2,00 unidades ..."]
}
```

`tipo` es `FAC`, `NC` o `ND`.

`data/ipc.csv` tiene las columnas `ym,ipc` y `data/ccl.csv` las columnas `ym,ccl`. Una fila por mes, `ym` en formato `AAAA-MM`. Las series se actualizan a mano y se versionan en el repo.

## Formato de salida

`out/ventas.csv` tiene catorce columnas:

```
ym, y, tipo, letra, fecha, cliente, cuit_cli, nro, concepto,
total, ccl, pesos_hoy, usd_epoca, usd_hoy
```

Al lado queda `out/ventas.csv.meta.json` con anclajes, conteos, `meses_sin_serie` y SHA-256.

`ventas.xlsx` tiene cinco hojas: Comprobantes, Resumen anual, Mensual, Clientes y Metodología. Los gráficos son objetos de Excel y se pueden editar.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Quince tests: determinismo (dos corridas, mismo SHA-256), notas de crédito negativas, fórmula de deflación contra el IPC del mes, anclaje de CCL, hueco interno como error, mes sin publicar, detección del CUIT del emisor, y que el resumen anual del libro cierre contra el CSV.

Los tests de extracción usan texto de ejemplo, no PDFs. Los de Excel se saltean si `openpyxl` no está instalado.

## Límites

- El CCL es promedio mensual, no la cotización del día del comprobante.
- El IPC se publica con un mes de rezago. Los comprobantes posteriores al último dato quedan en valores nominales hasta la próxima actualización de `data/ipc.csv`.
- Los regex de extracción corresponden al PDF estándar de AFIP. Un cambio de formato rompe la extracción. El paso de normalización no lee PDFs y no se ve afectado.
- El CUIT del emisor se lee del comprobante. Si un PDF no lo trae en su propia línea, se pasa con `--emisor`.

## Estructura

```
src/extraer.py       PDF → registros crudos (pypdf)
src/normalizar.py    registros + series → CSV (stdlib, sin red)
src/salidas.py       CSV → xlsx (openpyxl)
scripts/             generador del dataset sintético
data/                series IPC y CCL, muestra sintética
tests/               unittest
docs/esquema.md      notas de implementación
```

## Datos

`data/sample/datos.json` es sintético: nombres y CUIT inventados, importes generados con semilla fija. Las series de IPC y CCL son públicas.

## Licencia

MIT. Ver `LICENSE`.
