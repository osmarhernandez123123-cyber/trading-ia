# Auditoría sintética de presupuesto de riesgo OOS

`trading_ia.auditoria_riesgo_oos.auditar_riesgo_oos` revisa registros
**ya cerrados** de una ventana OOS; no consulta precios ni brokers, no
envía órdenes ni modifica el baseline V3.1.

Antes de analizar exposiciones, reutiliza `evaluar_prueba` para validar
fechas, zona horaria, R, riesgo, duplicados y pertenencia a prueba.
Con un capital inicial fijo de USD 100,000 y límites configurables de
**1% por operación y 3% simultáneo**, rechaza cualquier operación que
supere USD 1,000 de riesgo declarado y cualquier instante con más de
USD 3,000 de riesgo agregado declarado.

Se consideran posiciones en el intervalo **[entrada, salida)**: una salida
libera riesgo antes de una entrada con la misma marca de tiempo. Los
intervalos de duración cero no cuentan como exposición simultánea, pero
siguen sujetos al límite individual. El resultado devuelve el pico de
riesgo simultáneo en USD y como porcentaje del capital inicial, además
de una advertencia explícita. No modifica el DataFrame recibido.

```python
from trading_ia.auditoria_riesgo_oos import auditar_riesgo_oos

resultado = auditar_riesgo_oos(
    operaciones_oos, ventana_de_prueba, capital_inicial=100_000.0
)
```

**Alcance limitado:** este control utiliza **capital inicial fijo**.
El backtest puede presupuestar riesgo con patrimonio variable, por lo que
un rechazo aquí no prueba necesariamente que el motor haya incumplido
sus propias reglas dinámicas. No reconstruye stops ejecutados, PnL
flotante, gaps, deslizamiento, fills, operaciones omitidas ni riesgo de
correlación. Una auditoría exitosa solo valida el registro aportado;
no acredita rentabilidad ni cumplimiento operativo en vivo.

Tests sintéticos: `python -m pytest -q tests/test_auditoria_riesgo_oos.py`.
