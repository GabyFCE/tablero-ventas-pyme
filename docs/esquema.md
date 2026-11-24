# Notas de implementación

## Deflación por niveles

`data/ipc.csv` y `data/ccl.csv` guardan el valor mensual del índice, no la variación. El importe de cualquier mes se calcula contra el ancla en una sola operación:

```
pesos_hoy = total × IPC_ancla / IPC_mes
```

Si se corrige un dato de la serie, se edita esa fila y toda la salida se recalcula. Con variaciones acumuladas habría que recalcular la cadena desde el mes corregido.

## Anclaje

El ancla por defecto es el último mes con dato en cada serie. Se puede fijar con `--ipc-anchor` y `--ccl-anchor`. El valor usado se escribe en `ventas.csv.meta.json` con el SHA-256 del CSV, así la salida de un corte anterior se reproduce con los mismos números.

Sin ancla fija, "pesos de hoy" cambia cada vez que se actualiza la serie, incluso para comprobantes viejos.

## CCL mensual

Se usa el promedio del mes, no la cotización del día del comprobante. La serie de ventas es mensual y el promedio está en la tabla, versionado. Valuar un comprobante individual con este método da un número aproximado.

## Extracción

`extraer.py` transcribe campos: fecha, tipo, letra, número, cliente, CUIT, importes, ítems. No aplica signo a las notas de crédito, no convierte moneda y no redondea. El signo y el redondeo están en `normalizar.py`.

Consecuencia práctica: un cambio en el criterio contable se hace en un módulo y no altera la extracción ni sus tests.

## CUIT del emisor

En el PDF de AFIP el CUIT del emisor aparece solo en su línea; el del receptor aparece seguido del nombre del cliente. `emisor_de()` busca primero esa línea suelta y acepta el CUIT con o sin guiones.

Con el CUIT fijo en el código, un comprobante de otro emisor se registra con el CUIT propio y se suma al cliente equivocado.

## Alcance

El pipeline procesa ventas. No calcula costos ni márgenes, no concilia cobros y no publica en hojas de cálculo: la versión privada publica el CSV en Google Sheets, y esa parte queda afuera porque requiere credenciales propias.

Los datos reales tampoco están en el repo. Ver `README.md`, sección Datos.
