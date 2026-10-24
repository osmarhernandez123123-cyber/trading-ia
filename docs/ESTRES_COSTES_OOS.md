# Estrés de costes incrementales en OOS

`trading_ia.estres_costes_oos.evaluar_estres_costes` recibe operaciones **ya
cerradas** de una ventana de prueba `VentanaTemporal`, sin seleccionar señales
ni parámetros. Primero valida los trades originales con `evaluar_prueba`.
Después añade una penalización **hipotética** en puntos básicos (bps) por
lado y vuelve a calcular PnL, R, tasa de acierto y drawdown realizado.

```python
from trading_ia.estres_costes_oos import evaluar_estres_costes

reporte = evaluar_estres_costes(
    operaciones_oos, ventana,
    coste_extra_bps_lado=5.0,
)
print(reporte["baseline"]["expectativa_r"])
print(reporte["estresado"]["expectativa_r"])
```

Cada operación debe tener las columnas de `evaluar_prueba` y `nocional`
positivo, finito y en USD. `nocional` debe ser un valor numérico explícito:
se rechazan textos numéricos y booleanos, incluso si se podrían convertir a
`float`. También se rechazan costes no finitos por operación o por suma de
operaciones; se calcula primero el factor en bps para evitar desbordamientos
intermedios innecesarios en nocionales grandes. Se calcula:

```text
coste_extra_usd = 2 * nocional_entrada_usd * coste_extra_bps_lado / 10000
pnl_estresado = pnl_original - coste_extra_usd
R_estresado = pnl_estresado / riesgo_total_original
```

El factor 2 representa entrada y salida, **aproximando el mismo nocional en
ambos lados**. No se afirma que sea una simulación de fills: no incorpora
profundidad, impacto variable, borrow, margen ni precios reales de salida.
El PnL original ya incluye los costes modelados en el backtest; los bps
son una penalización **adicional**, no una nueva estimación total de costes.
Por ello un escenario de 0 bps reproduce exactamente el baseline.

Se preservan las operaciones de entrada y los resultados se calculan
exclusivamente en la ventana OOS. No usar el bloque de prueba para escoger
el coste, los parámetros o la estrategia; definir escenarios ex ante y
reportar todos, incluidos los negativos. No hay acceso a Alpaca, claves,
datos privados ni órdenes. Solo pruebas sintéticas en CI.
