# Auditoría aritmética de costes simulados vinculada a plan OOS

`auditar_costes_plan_oos(plan, plan_sha256_esperado=..., operaciones=...)`
verifica que un conjunto de operaciones sintéticas o ya calculadas declare
costes coherentes con el valor congelado `coste_bps_por_lado` del plan.

Exige por operación los campos numéricos `nocional_entrada_usd`,
`nocional_salida_usd`, `pnl_bruto_usd`, `coste_total_usd`,
`pnl_usd`, `riesgo_total` y `R`. Recalcula:

- `coste_total_usd = (nocional_entrada_usd + nocional_salida_usd) * bps / 10000`;
- `pnl_usd = pnl_bruto_usd - coste_total_usd`;
- `R = pnl_usd / riesgo_total`.

Las operaciones no se modifican. Se rechazan valores no numéricos, booleanos,
no finitos, nocionales/riesgos no positivos, costes negativos, errores de
contabilidad y huellas que no correspondan al plan. Tolerancia: coste y PnL
`rtol=1e-10, atol=1e-6`; R `rtol=1e-6, atol=1e-8`.

La huella debe haberse comprometido **externamente antes de observar OOS**.
La función no verifica cuándo se registró, ni que los nocionales o PnL bruto
procedan de operaciones reales, ni la autenticidad de los hashes declarados.
**No prueba fills, precios, slippage, costes del broker ni rentabilidad.**
Es una auditoría independiente: no se incorpora automáticamente al reporte
OOS existente ni cambia el baseline V3.1.

Los tests usan únicamente registros sintéticos, sin datos privados ni órdenes.
