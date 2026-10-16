## Problema y cambio
El pipeline dependía de rutas globales y mezclaba simulación con almacenamiento. Añade ejecución offline desde un dataset congelado y verificado por SHA-256, con versiones, parámetros, hashes y errores. Extrae motor V3.1 y transformaciones compartidas conservando parámetros y adaptador Parquet.

Corrige ausencia de operaciones tratada como fallo, candidatos descartados silenciosamente, timestamps desalineados y reemplazo del histórico tras descarga parcial. Añade contrato temporal para futuros eventos sin implementar decisiones automáticas.

## Validación
- 56 pruebas sintéticas aprobadas en Python 3.12.14; pip check correcto.
- Dos ejecuciones CLI completas: hashes lógicos idénticos en seis tablas.
- No hay datos históricos autorizados locales; no se afirma validación histórica, rentabilidad ni capacidad predictiva.
- Adaptadores externos revisados estáticamente; no se llamó a Alpaca ni se enviaron órdenes.

Ver AUDITORIA_FASE_3.md y docs/EJECUCION_FASE_3.md para hallazgos, procedimiento y limitaciones. Solo código, documentación y evidencia sintética; sin datasets privados ni secretos. Requiere revisión; no fusionar automáticamente.
