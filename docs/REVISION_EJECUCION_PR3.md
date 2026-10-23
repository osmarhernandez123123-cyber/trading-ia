# PR #3 — Auditoría temporal de la ejecución

Fecha: 2026-10-17. Referencia V3.1: commit `411f842`; se integraron también los commits remotos concurrentes hasta `c5c8e61`
(modelo por velas, CLI reproducible, pruebas, documentación y backlog), sin sobrescribirlos. No se fusiona con main.
Toda la comparación es sintética. Ningún resultado demuestra rentabilidad.

## Conclusión

El supuesto V3.1 es potencialmente optimista: conoce el primer precio del minuto
siguiente y dimensiona una orden que simula ejecutar en ese mismo evento, con
slippage fijo. No consulta high/low/close futuros para decidir la entrada, pero
eso **no basta** para establecer ejecución causal realizable. Observar el precio,
recibirlo, calcular niveles/cantidad, transmitir y obtener fill requieren tiempo.
No hay garantía de participar en el trade que acaba de revelar ese precio.

No puede medirse la magnitud ni el signo del efecto en mercado con estos datos.
Si el precio sube mientras una compra llega, el supuesto favorece al baseline;
si baja, puede perjudicarlo. En general no es correcto afirmar que cualquier
latencia reduce necesariamente el PnL. Los dos signos aparecen en las pruebas.
Tampoco el modelo alternativo demuestra fills reales o ausencia de todo sesgo.

## Qué información existe en cada instante

Las velas están etiquetadas por su **inicio**: la de 09:30 representa el intervalo
[09:30,09:31). Su close y los indicadores completos no son conocidos a las 09:30.

| Instante | Conocido | Aún desconocido |
| --- | --- | --- |
| Cierre nominal 09:31 de la vela 09:30 | OHLCV de esa vela, si ya fue recibido; dirección, ATR y distancia ATR×1.5 | Precio ejecutable posterior, spread, cantidad finalmente ejecutada |
| Recepción real de la vela cerrada | Señal utilizable tras el retardo del proveedor y procesamiento | Próxima cotización ejecutable |
| Primera cotización observada tras disponibilidad | Bid/ask de ese evento; midpoint de referencia, SL/TP y cantidad presupuestada | Cotización al llegar la orden y fill real |
| Llegada de la orden tras latencia positiva | Orden enviada con niveles/cantidad ya fijados | Profundidad suficiente, rechazo, fill parcial y precio efectivo |
| Evento posterior usado como fill simulado | Bid/ask observados en ese evento | Trayectoria posterior y capacidad real de ejecución |

En `preparar()`, `entrada_precio = open.shift(-1)` y los SL/TP son anotaciones
offline del escenario de ejecución, **no campos de una señal disponible al cierre**.
El cambio del open siguiente cambia esos niveles aunque la señal previa no cambie.
En `simular()`, entrada y tamaño dependen de esa apertura más slippage, antes de
examinar el movimiento intrabar. Esto idealiza una decisión y fill simultáneos.
Un sistema podría enviar de antemano una orden de mercado y offsets relativos al
fill, pero no conoce previamente su precio ni puede garantizar la cantidad exacta
que aquí se calcula a partir de él. Eso sería otro contrato de ejecución.

## V3.1 conserva comportamiento y parámetros por defecto

`preparar` y las fórmulas de señales/indicadores permanecen idénticos. Los commits
remotos ampliaron `Configuracion` y `simular` con `LATENCIA_VELAS=0/1`; cero
conserva V3.1 y uno habilita la variante por velas. Esta integración añade la
constante cero al adaptador histórico, evitando un `KeyError` al construir su
configuración. No se cambia el pipeline ni el modelo por defecto. Se mantienen capital 100000, riesgo 1%/3%, tres posiciones,
2 bps de slippage, comisión cero, ATR×1.5 y objetivo nominal 2R. Las pruebas previas
siguen vigentes. Se añaden hash de transformaciones, parámetros de referencia y resultados
sintéticos congelados para detectar cambios accidentales en V3.1. No se optimizan parámetros.

## Variante por velas integrada desde la rama remota

`trading_ia.ejecucion.preparar_diferido` fija niveles con el close de señal,
conserva ATR×1.5/2R y espera hasta `timestamp + 2 minutos`; exige barra intermedia.
Se utiliza con `Configuracion(LATENCIA_VELAS=1)` o la CLI
`trading_ia.investigacion --modelo-ejecucion diferido_1m`, integrada desde los
commits remotos. Se conservan sus pruebas y código.
No es equivalente a la variante por cotizaciones: cambia el ancla a close de
señal y usa una resolución temporal más gruesa. El motor sigue dimensionando a
la apertura de ejecución y puede rechazar la operación si el gap deja los niveles
fuera del rango válido. Si eso representa decidir tras observar esa apertura,
sigue siendo idealizado obtener fill en ella; si representa una orden ya enviada,
el rechazo retrospectivo puede introducir selección favorable. Por eso no se
presenta como solución completa de latencia ni se mezclan sus métricas con la
comparación de cotizaciones. La API de cotizaciones rechaza `LATENCIA_VELAS != 0`
para impedir combinar silenciosamente ambos contratos.

## Modelo alternativo explícito por cotizaciones

`trading_ia.ejecucion_latencia` es una API independiente, por sesión bursátil.
Requiere cotizaciones bid/ask con timestamps de disponibilidad/recepción en UTC o
con zona verificable. **No acepta OHLC como sustituto de ticks** ni reconstruye la
trayectoria interna de una vela real. No está conectado al pipeline por defecto.

1. `preparar_intenciones(senales)` consulta únicamente symbol, timestamp, dirección
   y ATR de la señal. Emite distancia y cierre nominal `timestamp + 1 minuto`.
   No necesita ni lee la vela siguiente. Conserva la condición original de cambio
   de señal por símbolo. No intenta recalcular señales a partir de ticks.
2. Se añade una demora de disponibilidad declarada (`demora_datos_ms`, >=0).
   La primera cotización recibida después del corte permite observar un precio.
   Se usa su **midpoint** como ancla nominal para SL/TP, con la misma distancia y
   relación 2R. En los fixtures sin spread ese midpoint coincide con el open
   sintético. Un midpoint real no equivale al primer trade de una vela: esa
   diferencia de ancla se declara y no se oculta como cambio de estrategia.
3. Se calcula la cantidad usando equity y reservas conocidas en ese instante,
   spread de ese instante y los 2 bps/las comisiones originales. Pendientes y
   posiciones consumen capacidad y riesgo. Niveles y cantidad quedan congelados.
4. `llegada_timestamp = envio_timestamp + latencia_ms`, estrictamente positiva.
   Se ejecuta la cantidad original en la primera cotización del símbolo recibida
   en o después de llegada: ask para LONG, bid para SHORT, más slippage adverso.
   Ningún high/low/close posterior decide el envío, precio o cantidad anteriores.
5. No se vuelve a centrar el bracket sobre el fill ni se redimensiona después de
   conocer el precio. Si se atraviesan niveles durante la espera, se asume el fill
   y se evalúa el bracket en ese nuevo evento; no se cancela a posteriori una
   orden porque su fill hubiera sido malo. Se registran nocional al fill y exceso
   respecto a reserva. Un gap puede exceder capital/riesgo previsto: no hay modelo
   de rechazo o margen de bróker y el resultado puede implicar financiación no
   disponible. Esa ejecución no se certifica como realizable.
6. Stops/objetivos se activan mediante bid/ask observados; no se inspeccionan los
   extremos anteriores al fill. Las salidas tienen **latencia cero** en esta API:
   es una limitación explícita, también al activarse inmediatamente el bracket.
7. Se programa liquidación desde el comienzo del último minuto oficial, conocido
   por calendario (15:59 o 12:59 en cierre anticipado). Se usa la primera cotización
   posterior disponible dentro de sesión. Es una convención distinta del close
   de última vela en V3.1, declarada para evitar mirar el último tick del dataset.
   Si faltan eventos para un fill o liquidación, se devuelve estado pendiente o
   posición abierta, sin inventar un cierre retroactivo. La comparación exige
   estado final vacío y contiene un precio constante durante el minuto final,
   de modo que esa convención no explica sus diferencias de PnL.

Los timestamps de órdenes incluyen señal, disponibilidad, observación, envío,
llegada y fill. No se supone que un instante de evento de mercado sea igual al
instante de recepción: quien aporte datos debe garantizar esa semántica. El
parámetro de demora no prueba ni estima la latencia real del feed.

## Experimento reproducible, exclusivamente sintético

```bash
.venv/bin/python -m trading_ia.comparar_ejecucion \
  --salida work/comparacion-ejecucion-nueva.json
.venv/bin/python -m pytest -q --junitxml=work/pruebas_revision_ejecucion.xml
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q trading_ia tests backtesting_v3_1.py
```

La CLI requiere salida inexistente. Genera explícitamente tres cotizaciones por
minuto (segundos 0, 1 y 59), deriva barras sintéticas de sus midpoints y aplica una
sola señal LONG fijada. No simula rentabilidad de la lógica de selección de señales:
la señal artificial aísla el contrato de ejecución. La sesión es XNYS 2026-01-05,
símbolo TEST. ATR=1/1.5, ancla en 100, niveles 99/102, precio final 101.5.
En 09:31:00 el midpoint es 100. Desde 09:31:01 se mueve 0, +0.5 o -0.5;
desde 09:32 es 101.5. Latencia ilustrativa 500 ms, **no calibrada**, demora de
feed cero; el muestreo sitúa el fill en 09:31:01 (1000 ms tras observar).

Se ejecutan cuatro escenarios predefinidos, sin búsqueda de combinaciones:

| Movimiento durante espera | Spread absoluto | PnL V3.1 USD | PnL alternativo USD | Diferencia USD |
| --- | ---: | ---: | ---: | ---: |
| 0 | 0 | 1402.77 | 1402.77 | 0.00 |
| +0.5 | 0 | 1402.77 | 922.18 | -480.60 |
| -0.5 | 0 | 1402.77 | 1883.37 | +480.60 |
| +0.5 | 0.1 | 1402.77 | 788.25 | -614.52 |

Son ganancias/pérdidas de **fixtures artificiales**, no rendimientos históricos.
El último escenario mezcla efecto del spread, cantidad presupuestada, y latencia;
no atribuir toda la diferencia a latencia. Los tres primeros aíslan la espera
bajo spread cero, mismo ancla y trayectoria común. El baseline permanece ajeno al
spread porque así está definido V3.1. Cada experimento tiene una operación.

`COMPARACION_EJECUCION_SINTETICA.json` contiene números sin redondear, hashes de
inputs y operaciones, configuración, versiones y trazas de las órdenes. La CLI
repite los experimentos completos y exige igualdad exacta entre ambos resultados.
El manifiesto de hashes protege reproducibilidad en el entorno fijado, no exactitud
del modelo. Los resultados V3.1 están congelados en el fixture de pruebas.

## Pruebas de causalidad y regresión

Se verifica que la intención es idéntica con o sin la siguiente vela, que cambiar
el open futuro altera solo el candidato retrospectivo V3.1, y que cambiar precios
tras el envío no altera niveles/cantidad previos. También se comprueba no usar
OHLC suministrado, no rellenar al precio anterior a la llegada, aceptar el evento
exacto de llegada, no aplicar extremos previos al fill, retrasar la observación
cuando el feed tarda, reservar capital de órdenes pendientes, proteger los límites
de posiciones/riesgo presupuestado y mantener determinismo entre órdenes de input.
Se cubren LONG/SHORT, spread, gaps, stops, cierre temprano, falta de ticks finales,
latencia inválida, timestamps sin zona y señales con disponibilidad adelantada.

Las regresiones protegen transformaciones, parámetros originales, selección por
defecto de V3.1 y resultados congelados. Esto complementa la suite previa, no sustituye su cobertura.

## Límites que impiden afirmar realizabilidad

- OHLC no contiene orden de trades, bid/ask, profundidad ni recepción. No permite
  estimar esta corrección sin datos adicionales. No se han descargado datos reales.
- Los bid/ask observados no garantizan poder consumir esa liquidez. Se asume fill
  completo instantáneo, sin volumen, cola, impacto, rechazos o fills parciales.
- El spread explícito más 2 bps es una convención experimental, no una calibración.
  El feed sintético es más limpio que uno real: sin quotes stale, out-of-order,
  relojes desincronizados, actualizaciones simultáneas ambiguas ni correcciones.
- La latencia configurada se redondea hacia el siguiente evento observado; no se
  interpola un precio. Datos dispersos alteran la latencia efectiva.
- No hay retardo de confirmación, cancelación ni activación real de brackets.
  Salidas y liquidación conservan supuestos favorables de latencia cero.
- Un gap puede romper presupuesto y reservas con cantidad fijada. Falta un modelo
  de riesgo/margen del intermediario; no se deben equiparar resultados a capital
  financiable ni truncar pérdidas para forzar cumplimiento.
- La API alternativa rechaza datasets con varias fechas para exigir simulación
  explícita por sesión; no tiene carry de posiciones, borrow, funding o corporate
  actions. El resultado abierto/pendiente al final nunca se considera liquidado.
- Prioridad alfabética y snapshots bid/ask definen un orden artificial cuando hay
  simultaneidad. No reproduce matching ni subastas.

## Criterio para la revisión

V3.1 queda identificado como benchmark idealizado, no como validación de una
entrada realizable. El modelo alternativo es una herramienta de sensibilidad
causal, optativa y sin cambiar la estrategia por defecto. Antes de interpretar
métricas económicas se necesitan timestamps de recepción verificables, quotes o
trades autorizados y reglas de ejecución calibradas fuera de muestra. Esta
revisión no recomienda parámetros, no estima edge y no autoriza operaciones.

## Resultado de validación local

```text
python -m pytest -q --junitxml=work/pruebas_revision_ejecucion.xml
91 passed, 1 warning in 25.59s
python -m pip check
No broken requirements found.
python -m compileall -q trading_ia tests backtesting_v3_1.py
Exit 0
git diff --check
Exit 0
```

La suite integra también las seis pruebas concurrentes del modelo por velas.
El fixture económico V3.1 y la selección por defecto se verifican explícitamente. La advertencia sigue
siendo la deprecación transitiva `websockets.legacy` del SDK en la prueba con
proveedor simulado, sin llamadas a servicios. La comparación completa se ejecutó
dos veces con igualdad exacta. Esta evidencia es local; el estado de CI remota
se informa en el PR y debe revisarse para el commit publicado.
