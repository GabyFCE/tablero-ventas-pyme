# Esquema y decisiones

## Por qué niveles y no porcentajes

Guardar la variación mensual del IPC y multiplicar acumulando parece más simple, pero cada vez que INDEC revisa un dato hay que recalcular toda la cadena hacia adelante, y el error de un mes se propaga a todos los siguientes sin dejar rastro. Con niveles, el valor de cualquier mes se calcula directo contra el ancla:

```
pesos_hoy = total × IPC_ancla / IPC_mes
```

Si mañana se corrige el IPC de marzo de 2023, se corrige una fila de `data/ipc.csv` y la serie entera se recalcula sola.

## Por qué el ancla es explícita

Sin ancla fija, "pesos de hoy" significa "pesos del día en que corriste el script". Dos corridas con una semana de diferencia dan números distintos y no se puede comparar un tablero con un informe anterior.

El ancla es el último mes de IPC disponible, salvo que se fije a mano. Queda escrita en `ventas.csv.meta.json` junto al SHA-256 del CSV, así un tablero publicado se puede reproducir exactamente:

```bash
python3 src/normalizar.py --ipc-anchor 2026-10 --ccl-anchor 1693.29
```

## Por qué el CCL es promedio mensual

La serie de ventas es mensual; mezclar la cotización del día de cada comprobante introduce ruido que no aporta a la comparación entre meses y hace imposible reproducir el número sin la cotización exacta de ese día. El promedio mensual está en la tabla, versionado, y el ancho de la banda queda a la vista en la hoja Mensual.

## Por qué el extractor no interpreta

`extraer.py` transcribe: fecha, tipo, letra, número, cliente, CUIT, importes, ítems. No firma notas de crédito, no convierte, no redondea. El signo de las NC se aplica en `normalizar.py`, que es donde vive la regla contable.

La ventaja es de mantenimiento: si cambia el criterio de signo o de redondeo, se toca un solo módulo, y los tests de la capa de extracción no se mueven.

## Por qué el emisor se lee del comprobante

En el PDF de AFIP el bloque del emisor trae su CUIT solo en una línea; el del receptor viene seguido del nombre. Eso alcanza para distinguirlos. Tener el CUIT emisor como constante funciona hasta el día en que entra un comprobante de otro emisor (una compra, una nota de un tercero) y se contabiliza contra el cliente equivocado sin que nadie lo note.

## Qué queda afuera a propósito

- **Costos y márgenes.** El pipeline sólo sabe de ventas.
- **Conciliación bancaria.** Que la factura esté cobrada es otro sistema.
- **Publicación en hojas de cálculo.** La versión privada de este pipeline publica el CSV en Google Sheets; esa parte no está acá porque requiere credenciales de cada usuario. El CSV y el xlsx son el punto de salida.
- **Datos reales.** Ver `README.md`, sección Datos.
