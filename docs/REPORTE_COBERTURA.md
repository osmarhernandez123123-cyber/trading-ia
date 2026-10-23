# Cobertura de datasets intradía — diagnóstico local

El comando inspecciona **solo archivos locales CSV o Parquet** y genera un
reporte agregado JSON de barras observadas frente a minutos esperados del
calendario XNYS/XNAS. No necesita credenciales, no consulta servicios y no
sube los precios a GitHub.

Ejemplo con CSV:

    python -m trading_ia.reporte_cobertura datos/aapl_msft.csv \
      --fuente IEX --calendario XNYS \
      --inicio 2026-01-05 --fin 2026-01-09 \
      --salida reportes/cobertura.json

También admite archivos .parquet. La CLI calcula el SHA-256 de los **bytes
exactos del archivo local** y registra `archivo_sha256` y `archivo_bytes` en
el JSON, sin publicar rutas ni precios. Para comprobar una copia contra una
huella conocida antes de analizarla, usar:

    python -m trading_ia.reporte_cobertura datos/aapl_msft.csv \
      --fuente IEX --sha256-esperado <64_caracteres_hex> \
      --salida reportes/cobertura.json

Si la huella no coincide, se rechaza el archivo y no se genera el reporte.
También se impide que `--salida` sobrescriba el dataset de entrada,
incluso si el destino es un enlace duro al archivo original. Se vuelve a
comprobar el SHA-256 y el tamaño después de leer: si el archivo cambió, se
rechaza el reporte. Esta doble comprobación **no equivale a una lectura
atómica**: para un dataset modificado simultáneamente por otro proceso,
trabajar sobre una copia inmutable. El hash demuestra identidad de bytes,
**no** legitimidad, calidad ni procedencia del proveedor: conservar un
manifiesto de origen y licencia aparte.

El archivo debe tener columnas symbol y
timestamp; cada timestamp debe incluir zona horaria explícita, por ejemplo
2026-01-05T14:30:00Z. Los valores sin zona horaria se rechazan en lugar de
asumir UTC. Las fechas de inicio y fin son fechas de sesión en Nueva York.

**Es importante declarar inicio y fin** cuando se quieran detectar días
completamente ausentes en los extremos: sin ellos se infiere el intervalo
únicamente desde los timestamps observados. Un símbolo sin ninguna fila en
todo el archivo no se puede descubrir sin un universo de símbolos externo.

El reporte distingue:

- Minutos esperados, presentes y ausentes por símbolo y sesión.
- Sesiones completas, incompletas, sin datos y con cierre anticipado legítimo.
- Filas fuera de la sesión regular, que no se cuentan como cobertura regular.
- Proporción de cobertura agregada y por símbolo.

Las ausencias **no demuestran** un fallo de IEX u otro proveedor: pueden ser
minutos sin transacciones, pérdida de datos, interrupciones o datos truncados.
La herramienta no atribuye causas, no interpola velas y no modifica el dataset.
El campo fuente es una etiqueta proporcionada por el usuario, no una prueba
de procedencia. El reporte no reemplaza la validación OHLCV, los manifiestos
SHA-256 ni el análisis de licencia y corporate actions.

Pruebas sintéticas locales:

    python -m pytest -q tests/test_reporte_cobertura.py

No incluir CSV/Parquet privados ni reportes con información sensible en
commits o PR sin comprobar previamente sus derechos de distribución.
