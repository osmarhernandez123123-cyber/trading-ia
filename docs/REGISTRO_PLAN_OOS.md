# Registro previo de experimentos OOS (esquema 1)

`trading_ia.registro_plan_oos.registrar_plan_oos(plan)` valida un plan
**antes de mirar la prueba fuera de muestra** y devuelve una versión
normalizada con su SHA-256 determinista. Solo utiliza biblioteca estándar,
no lee históricos, no conecta brokers y no escribe archivos.

## Contrato mínimo

El argumento `plan` es un diccionario con exactamente estos campos:

- `schema_version=1`; `dataset_sha256` del histórico inmutable.
- `baseline_id`, `candidata_id`, identificadores distintos.
- `baseline_parametros_sha256` y `candidata_parametros_sha256` de las
  configuraciones congeladas **fuera** del conjunto OOS.
- `universo`: símbolos explícitos, únicos, en mayúsculas (p. ej. AAPL, MSFT).
- `inicio_prueba`, `fin_prueba`: fechas ISO YYYY-MM-DD.
- `coste_bps_por_lado`: coste adicional supuesto, finito y no negativo.
- `ventanas`: `entrenamiento`, `validacion`, `prueba`, `embargo`,
  `horizonte_etiqueta`, `paso` (enteros positivos); embargo debe cubrir
  horizonte de etiqueta y paso debe ser >= prueba.
- `hipotesis`: texto breve predefinido (máximo 500 caracteres).

Se rechazan campos adicionales, incluidas métricas de resultados, fechas
inválidas, duplicados, costes no finitos y ventanas solapadas. El universo se
ordena y el coste se normaliza a `float`, para evitar huellas distintas por
el orden de símbolos o por usar `2` frente a `2.0`. La huella se calcula
sobre JSON UTF-8 con claves ordenadas y separadores compactos.

## Procedimiento reproducible

1. Definir hipótesis, símbolos, fechas, costes, parámetros y hashes sin
   consultar resultados del bloque de prueba.
2. Ejecutar `registrar_plan_oos(plan)`; guardar **fuera de este módulo**
   tanto `plan` normalizado como `plan_sha256` en un registro fechado e
   inmutable **antes** de evaluar OOS. No registrar secretos ni datos
   licenciados sin autorización.
3. Ejecutar el experimento con los parámetros previamente congelados.
4. Recalcular la huella sobre el plan usado y compararla con el registro.
   Si difiere, tratarlo como experimento distinto, no como prueba original.

La función **no puede verificar** si los hashes declarados corresponden a
archivos reales, si el registro es anterior a los resultados o si la selección
del universo es point-in-time. Tampoco impide consultar OOS antes de registrar
el plan, ni demuestra rentabilidad o significancia estadística. Requiere
integración posterior con el laboratorio y una política externa de custodia.
