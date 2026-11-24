# tablero-ventas-pyme

Convierte comprobantes de AFIP (PDF) en una serie de ventas comparable en el tiempo: nominal, pesos de hoy y dólares, con la trazabilidad de cada número.

## El problema

Una PyME factura en pesos. Comparar 2020 con 2026 con los importes de los comprobantes no dice nada: la inflación y el tipo de cambio se comen la comparación. Y el error típico no está en extraer los datos, está en el ajuste: aplicar porcentajes acumulados mes a mes arrastra el error de cada revisión del índice, y nadie lo nota porque el total sigue pareciendo razonable.

Este pipeline toma tres decisiones:

1. **Niveles, no porcentajes.** Se guardan los índices mensuales y se divide por el valor del mes. Un deflactor se recalcula entero cuando INDEC revisa un dato; una suma de porcentajes no.
2. **Anclajes explícitos.** El mes de IPC y el CCL de referencia quedan escritos en el archivo de salida. Correr el mismo corte dentro de un año tiene que dar lo mismo.
3. **Determinista y sin red.** Mismos datos, mismas tablas, mismo archivo. Las series se actualizan aparte y se versionan acá.

## Cómo corre

```
PDF AFIP ──extraer.py──▶ datos.json ──normalizar.py──▶ ventas.csv ──salidas.py──▶ ventas.xlsx
                                                          ▲
                                          data/ipc.csv ───┤
                                          data/ccl.csv ───┘
```

```bash
# 1. comprobantes → registros crudos (requiere pypdf)
python3 src/extraer.py --pdfs comprobantes/ --salida datos.json

# 2. registros + series → serie comparable (sin dependencias)
python3 src/normalizar.py --datos datos.json --salida out/ventas.csv

# 3. serie → libro de Excel (requiere openpyxl)
python3 src/salidas.py --csv out/ventas.csv --xlsx out/ventas.xlsx
```

Sin comprobantes a mano, el repo trae un dataset sintético con la misma forma:

```bash
python3 scripts/generar_muestra.py          # 137 comprobantes inventados
python3 src/normalizar.py                   # usa data/sample/datos.json por defecto
python3 src/salidas.py
python3 -m unittest discover -s tests
```

## Fórmulas

Con `IPC` e `CCL` como niveles mensuales:

```
pesos_hoy = total × (IPC_ancla / IPC_mes)
usd_epoca = total / CCL_mes
usd_hoy   = pesos_hoy / CCL_ancla
```

Las notas de crédito entran en negativo antes de cualquier cálculo, así los totales cierran con la cuenta corriente.

Un mes posterior al último dato publicado no rompe la corrida: usa el último valor de la serie, queda en términos nominales y se informa en `meses_sin_serie`. Un hueco en el medio sí es error: significa que falta un dato, no que el mes sea reciente.

## Contrato de datos

`datos.json`: lista de registros, uno por comprobante.

```json
{
  "file": "20111111112_001_00001_00000123.pdf",
  "emisor": "20111111112",
  "tipo": "FAC",            // FAC | NC | ND
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

`data/ipc.csv` → `ym,ipc` · `data/ccl.csv` → `ym,ccl`. Un registro por mes, `ym` en formato `AAAA-MM`.

`out/ventas.csv` trae una fila por comprobante y catorce columnas: `ym, y, tipo, letra, fecha, cliente, cuit_cli, nro, concepto, total, ccl, pesos_hoy, usd_epoca, usd_hoy`. Al lado queda `ventas.csv.meta.json` con los anclajes usados, los conteos y el SHA-256 del CSV.

## Reproducir un corte viejo

```bash
python3 src/normalizar.py --ipc-anchor 2026-08 --ccl-anchor 1628
```

Cambia los valores en pesos y dólares de hoy, no las filas ni los nominales. Sirve para auditar un tablero que se publicó meses atrás.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Cubren: determinismo (dos corridas, mismo SHA-256), NC negativas, la fórmula de deflación contra el IPC del mes, el anclaje de CCL, el hueco interno como error, el mes sin publicar, la detección del CUIT del emisor y que el libro cierre contra el CSV.

Los de extracción prueban funciones puras: no hacen falta PDFs. Los de Excel se saltean si `openpyxl` no está instalado.

## Límites

- **El CCL es promedio mensual**, no la cotización del día del comprobante. Para una serie mensual alcanza; para valuar una factura puntual no.
- **El IPC llega con un mes de rezago.** Los comprobantes de ese mes y del siguiente quedan en valores nominales hasta la próxima actualización de `data/ipc.csv`.
- **La extracción depende del layout de AFIP.** Los regex están escritos contra el PDF estándar de comprobante. Si cambia el formato, se rompe la extracción — el núcleo no: recibe `datos.json` y no sabe de PDFs.
- **El emisor se detecta del comprobante**, no se asume. Si un PDF no lo trae suelto, `--emisor` lo fuerza.

## Estructura

```
src/extraer.py      PDF → registros crudos (pypdf, opcional)
src/normalizar.py   registros + series → CSV (stdlib, sin red)
src/salidas.py      CSV → xlsx con gráficos nativos (openpyxl)
scripts/            generador del dataset sintético
data/               series públicas versionadas + muestra sintética
tests/              unittest, sin dependencias externas
```

## Datos

El repo no incluye datos de ningún contribuyente. `data/sample/datos.json` es sintético: nombres y CUIT inventados, importes sorteados con semilla fija. Las series de IPC y CCL son públicas.

## Licencia

MIT. Ver `LICENSE`.
