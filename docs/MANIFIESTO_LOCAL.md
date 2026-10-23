# Manifiesto local de procedencia declarada

Esta herramienta **no descarga ni publica datos**. Toma el JSON de cobertura
generado por `trading_ia.reporte_cobertura` y produce un manifiesto con:
fuente declarada, licencia/permiso de uso declarado, política de ajustes,
zona horaria declarada de timestamps, versión del dataset, SHA-256 y tamaño
del archivo de datos, y resumen de cobertura por calendario.

## Uso local

Primero generar el reporte de cobertura con un archivo propio, sin subirlo:

```bash
python -m trading_ia.reporte_cobertura datos/acciones.csv \
  --fuente IEX --inicio 2026-01-05 --fin 2026-01-09 \
  --salida reportes/cobertura.json
```

Después generar el manifiesto (la salida debe ser una ruta nueva):

```bash
python -m trading_ia.manifiesto_local \
  --reporte reportes/cobertura.json \
  --fuente-esperada IEX \
  --licencia "uso interno, verificar contrato con proveedor" \
  --ajuste sin_ajuste \
  --zona-timestamps UTC \
  --version-dataset iex-2026-01-v1 \
  --salida reportes/manifiesto-v1.json
```

`--ajuste` admite `sin_ajuste`, `split`, `split_dividendo` u `otro`.
La versión debe ser identificable y no contener espacios ni rutas.
`--zona-timestamps` es la zona **declarada** de los datos originales,
que deben tener timestamps con offset o zona explícita; no convierte fechas.

El programa verifica la coherencia de los conteos entre sesiones, símbolos
y resumen, y exige una huella SHA-256 válida en el reporte. Incluye además
el SHA-256 de los bytes del propio reporte de cobertura para enlazar ambos
documentos. No incluye rutas locales, barras OHLCV ni claves.

**Límites:** todos los metadatos son declaraciones del operador, no
verificaciones de origen, permiso de redistribución, tratamiento de splits,
identidad de proveedor ni versión real. El manifiesto no vuelve a abrir el
dataset: para garantizar que corresponde al archivo actual, ejecutar primero
la cobertura con `--sha256-esperado` y una copia inmutable. El SHA-256 no
impide sustituciones si alguien controla simultáneamente archivo y reporte.
No subir reportes ni manifiestos que puedan revelar información sensible
sin revisar los derechos de distribución.

Pruebas sin red:

```bash
python -m pytest -q tests/test_manifiesto_local.py
```
