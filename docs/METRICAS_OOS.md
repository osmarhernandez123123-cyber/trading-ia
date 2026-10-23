# Métricas descriptivas fuera de muestra (OOS)

`trading_ia.metricas_oos.evaluar_prueba(operaciones, ventana)` resume las
operaciones cerradas de **una sola ventana de prueba** producida por
`trading_ia.validacion_temporal.crear_ventanas`. No descarga precios, no
entrena, no escoge estrategias ni interactúa con Alpaca.

El DataFrame debe incluir `symbol`, `entrada_timestamp`,
`salida_timestamp`, `pnl_usd`, `riesgo_total` y `R`, tal como el motor
`trading_ia.backtest.simular`. Requiere timestamps con zona explícita,
entradas y salidas en las sesiones de prueba (fecha de Nueva York), cierre
en la misma sesión, riesgo estrictamente positivo y R consistente con
`pnl_usd / riesgo_total`. **No filtra silenciosamente** operaciones de
entrenamiento, validación, embargo ni fuera de prueba: las rechaza.

Ejemplo de integración local, después de ejecutar un backtest por separado:

```python
from trading_ia.metricas_oos import evaluar_prueba

# ventana: objeto VentanaTemporal ya construido
# operaciones: DataFrame devuelto por el backtest, solo de prueba
reporte = evaluar_prueba(operaciones, ventana, capital_inicial=100_000)
print(reporte)
```

Métricas: número de trades, ganadoras/perdedoras/neutras, PnL realizado
(ya neto de los costes **que el backtest realmente modeló**), retorno
realizado sobre capital inicial, tasa de acierto, media de R y máximo
drawdown calculado sobre el capital realizado al cerrar trades.
Para cero operaciones, tasa de acierto y expectativa son `None` y
no se declara éxito ni fracaso.

**Limitaciones críticas:** el drawdown realizado puede ser mucho menor
que el drawdown mark-to-market, porque ignora pérdidas flotantes y
movimientos intrabar. El retorno no está anualizado y no modela
reinversión ni exposición. El simulador no representa necesariamente
todos los costes de mercado. La media de R de pocas operaciones es
estadísticamente inestable. Esta función no calcula intervalos de
confianza ni certifica rentabilidad. La selección de parámetros debe
terminar antes de mirar el bloque de prueba; repetir ajustes después
de ver resultados OOS invalida la independencia de esa prueba.

Pruebas sintéticas:

```bash
python -m pytest -q tests/test_metricas_oos.py
```
