# tablero-ventas-pyme

Pipeline de extracción y ajuste por inflación de comprobantes electrónicos de AFIP en PDF para análisis de facturación de PyMEs en moneda constante.

## Qué es y para qué sirve

La inflación distorsiona la comparación de ventas nominales entre distintos períodos: un mes de 2021 y uno del año en curso no son comparables sin ajuste. Este proyecto lee comprobantes de AFIP en formato PDF, extrae los campos fiscales y cruza cada operación con series mensuales de IPC y dólar Contado con Liquidación (CCL).

El proceso genera un archivo CSV con una fila por comprobante (importe nominal, importe en pesos del mes de referencia e importes en dólares) y un libro de Excel con tablas agregadas y gráficos editables.

```
PDF ──extraer.py──▶ datos.json ──normalizar.py──▶ ventas_normalizadas.csv ──salidas.py──▶ ventas.xlsx
                                        ▲
                          data/ipc.csv ─┤
                          data/ccl.csv ─┘
```

Fórmulas aplicadas sobre los niveles mensuales de cada serie (las notas de crédito ingresan en negativo antes del cálculo):

```
pesos_hoy = total × (IPC_ancla / IPC_mes)
usd_epoca = total / CCL_mes
usd_hoy   = pesos_hoy / CCL_ancla
```

## Qué incluye

| Componente | Entrada | Salida | Detalle |
| --- | --- | --- | --- |
| `src/extraer.py` | Directorio de PDFs | `datos.json` | Extrae emisor, tipo (`FAC`, `NC`, `ND`), letra, fecha, montos, cliente, CUIT e ítems. |
| `src/normalizar.py` | `datos.json`, `ipc.csv`, `ccl.csv` | `out/ventas_normalizadas.csv` y `.meta.json` | Calcula 14 columnas y registra en el archivo meta los anclajes, conteos, `meses_sin_serie` y el SHA-256 del CSV. |
| `src/salidas.py` | `out/ventas_normalizadas.csv` | `out/ventas.xlsx` | Genera cinco hojas: Comprobantes, Resumen anual, Mensual, Clientes y Metodología. |
| `scripts/generar_muestra.py` | Semilla fija | `data/sample/datos.json` | Genera 137 registros sintéticos para pruebas sin comprobantes reales. |
| `tests/` | Texto y datos de prueba | Reporte por consola | 15 pruebas sobre determinismo, notas de crédito, deflación, huecos de serie y cierre del resumen anual. |

## Decisiones técnicas

- **Normalización solo con la biblioteca estándar:** `src/normalizar.py` no utiliza paquetes externos ni conexiones de red, en lugar de depender de librerías externas de análisis de datos. Esto permite auditar y ejecutar el cálculo financiero sin instalar dependencias ni exponer datos fiscales.
- **Etapas desacopladas por archivos intermedios:** La extracción desde PDF (`pypdf`), el cálculo y el armado de Excel (`openpyxl`) se ejecutan por separado, en lugar de integrar todo en un único proceso. Si cambia el formato del PDF de AFIP, se adapta `src/extraer.py` sin alterar el motor de cálculo; si `openpyxl` no está instalado, las pruebas de Excel se omiten sin bloquear la validación del CSV.
- **Series de IPC y CCL en archivos CSV locales:** Las series (`ym,ipc` e `ym,ccl` en formato `AAAA-MM`) se actualizan a mano y se versionan en el repositorio, en lugar de consultar APIs externas en tiempo de ejecución. Esto garantiza determinismo (dos corridas producen el mismo SHA-256). Si falta un mes intermedio, la ejecución se detiene con error; si un comprobante es posterior al último mes publicado, utiliza el último valor disponible y queda registrado en `meses_sin_serie`.
- **CCL como promedio mensual:** Se utiliza el promedio del mes del comprobante en lugar de la cotización diaria, manteniendo la misma granularidad mensual que la serie del IPC.

## Estructura

```
LICENSE                         Licencia MIT
data/ccl.csv                    Serie histórica mensual de dólar CCL (ym,ccl)
data/ipc.csv                    Serie histórica mensual de IPC (ym,ipc)
data/sample/datos.json          Muestra sintética de 137 comprobantes
docs/esquema.md                 Notas de implementación y detalle de formatos
scripts/generar_muestra.py      Generador del conjunto de datos sintético con semilla fija
src/extraer.py                  Extractor de campos desde PDFs de AFIP a JSON
src/normalizar.py               Cálculo de moneda constante y generación de CSV y metadatos
src/salidas.py                  Generador del libro de Excel de cinco hojas desde el CSV
tests/test_extraer_y_salidas.py Pruebas de extracción de texto y generación de Excel
tests/test_normalizar.py        Pruebas de cálculo, anclajes, determinismo y validación de series
```

## Cómo se usa

Requiere Python 3.9 o superior. Instalar las dependencias para lectura de PDF y escritura de Excel:

```bash
pip install pypdf openpyxl
```

Ejecución con comprobantes propios en PDF:

```bash
python3 src/extraer.py --pdfs comprobantes/ --salida datos.json
python3 src/normalizar.py --datos datos.json --salida out/ventas_normalizadas.csv
python3 src/salidas.py --csv out/ventas_normalizadas.csv --xlsx out/ventas.xlsx
```

Si un PDF no incluye el CUIT del emisor en su propia línea, se especifica con `--emisor`. Para fijar manualmente el mes de referencia de IPC y el valor de CCL en lugar de usar el último mes publicado:

```bash
python3 src/normalizar.py --ipc-anchor 2026-10 --ccl-anchor 1693.29
```

Ejecución de extremo a extremo con la muestra sintética y corrida de las 15 pruebas unitarias:

```bash
python3 scripts/generar_muestra.py
python3 src/normalizar.py
python3 src/salidas.py
python3 -m unittest discover -s tests -v
```

## Estado del contenido

El repositorio no incluye comprobantes reales. El archivo `data/sample/datos.json` contiene 137 registros sintéticos con razones sociales, números de CUIT e importes generados mediante semilla fija. Las series en `data/ipc.csv` y `data/ccl.csv` contienen datos públicos reales.

## Licencia

MIT. Ver `LICENSE`.
