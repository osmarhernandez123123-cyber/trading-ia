# Reporte OOS vinculado a un plan congelado

`trading_ia.reporte_plan_oos.comparar_plan_registrado_oos` conecta el registro
canónico del PR #17 con la comparación descriptiva del PR #15, sin leer datos,
llamar a brokers ni modificar el baseline V3.1.

## Contrato

La función recibe:

- Un plan con el esquema exacto de `registrar_plan_oos`.
- `plan_sha256_esperado`, copiado de un compromiso **externo y anterior a la
  observación de OOS**; no calcularlo en el mismo instante de la comparación
  como supuesto comprobante de pre-registro.
- Una secuencia estrictamente ordenada y **completa** de sesiones del
  calendario XNYS entre su primera y última fecha. Se rechazan fines de
  semana, festivos, fechas omitidas y rangos fuera del calendario.
- Dos secuencias de DataFrames de operaciones intradía, una por estrategia,
  en el orden de las ventanas construidas con el plan.

Antes de evaluar métricas, la función verifica la huella SHA-256, reconstruye
las ventanas a partir de la configuración declarada, comprueba que el inicio
y fin de prueba correspondan a las fechas registradas, exige un bloque por
ventana y rechaza símbolos ajenos al universo congelado. También exige que
cada entrada esté dentro de la sesión regular XNYS **antes del cierre** y
que cada salida ocurra entre apertura y cierre inclusive, respetando cierres
anticipados (por ejemplo, 13:00 hora de Nueva York el día posterior a
Thanksgiving). Los validadores OOS existentes revisan timestamps, riesgo,
R, duplicados y ausencia de posiciones nocturnas. Devuelve el plan
normalizado, su huella y el resultado descriptivo.

## Uso (sin ejecutar órdenes)

```python
from trading_ia.reporte_plan_oos import comparar_plan_registrado_oos

reporte = comparar_plan_registrado_oos(
    plan_predefinido,
    plan_sha256_esperado=huella_externa_previa,
    sesiones=sesiones_bursatiles_verificadas,
    baseline_por_ventana=operaciones_baseline,
    candidata_por_ventana=operaciones_candidata,
)
```

Los tests de `tests/test_reporte_plan_oos.py` usan fechas de sesiones XNYS
reales con **operaciones y resultados completamente sintéticos**; no
constituyen evidencia de una ventaja económica.

## Límites

La comparación no verifica que los hashes declarados correspondan a archivos
reales, que el universo haya sido conocido point-in-time, que los costes
correspondan a fills, ni que el compromiso se haya publicado antes de
observar resultados. La validación de calendario y horarios comprueba sesiones XNYS y límites
de apertura/cierre de cada operación, incluidos cierres anticipados; **no**
verifica la existencia de transacciones o barras en cada minuto, ni fills,
slippage, costes netos, cobertura intradía, calidad de barras, procedencia
ni licencia del dataset.
No impide que alguien cambie simultáneamente el plan y la huella suministrada;
esa amenaza requiere un registro externo inmutable y fechado. No se calculan
p-valores ni se elige un ganador. Una comparación con datos sintéticos no
demuestra rentabilidad.
