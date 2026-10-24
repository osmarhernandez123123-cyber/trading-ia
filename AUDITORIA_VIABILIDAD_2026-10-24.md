# TRADING IA — Auditoría crítica de viabilidad económica

**Fecha:** 2026-10-24. **Alcance:** inspección estática del repositorio privado `main`, auditorías Fases 1/3, parámetros de V3.1, estado de PR #1–#33 y contraste con literatura. **Sin acceso a datos privados ni ejecución con históricos reales.**

## Dictamen ejecutivo: NO GO operativo / GO condicional de investigación

- **NO GO** para operar con dinero real o virtual, para atribuir rentabilidad a V3.1 y para continuar ampliando funciones sin pruebas económicas.
- **NO GO** para considerar V3.1 una estrategia rentable: la evidencia disponible no lo demuestra. La evaluación histórica preliminar reportada (~812 operaciones, ~35.3% aciertos, ~−20.8% rendimiento acumulado y ~−0.2766 R/operación) fue negativa y **no se reproduce desde el repositorio**. Tratar cifras como antecedentes no verificados, no como resultados auditados.
- **GO condicional** para conservar el software como banco de investigación, limitado a un experimento reproducible que pueda producir un resultado negativo y terminar el proyecto si corresponde.
- El número de commits, PR integradas, tests sintéticos, hashes, métricas descriptivas OOS o un eventual resultado de Alpaca Paper **no acredita ventaja estadística ni rentabilidad**.

## Hechos verificados en el proyecto

1. `trading_ia/transformaciones.py`: V3.1 utiliza EMA9/EMA21, RSI14, ATR14, VWAP diario y volumen relativo; habilita LONG/SHORT por confluencia, de lo contrario NO TRADE.
2. `trading_ia/backtest.py`: capital de referencia 100 000 USD, riesgo presupuestado por operación 1%, agregado 3%, hasta 3 posiciones, slippage fijo 2 bps, comisión 0; stop a 1.5×ATR, objetivo nominal 2R. No modela plenamente libro de órdenes, borrow fees, profundidad, dividendos, impacto, latencia ni margen del broker.
3. `docs/REVISION_EJECUCION_PR3.md`: el modelo original fija niveles/tamaño con el precio de apertura de la misma vela en que supone ejecución, un supuesto de fill idealizado. Alternativas sintéticas con cotizaciones/latencia sirven para cuestionar ese supuesto, no para probar el PnL realizable.
4. `AUDITORIA_FASE_1.md`: los ~812 trades/resultados históricos **no pudieron reproducirse** porque faltan Parquet fuente, huellas y artefactos originales. Las auditorías certifican coherencia de pruebas sintéticas, no rentabilidad.
5. `AUDITORIA_FASE_3.md` y `RESULTADOS_FASE_3.md`: pruebas con datos inventados (símbolo TEST/serie artificial) y cobertura de código; no validación OOS con mercados históricos reales.
6. `PLAN_DESARROLLO_AUTONOMO.md`: ~30 días de IEX AAPL/MSFT/NVDA permanecen en el Mac del usuario, no accesibles desde GitHub; sesgos por huecos, cobertura y procedencia requieren revisión. PR #5 con Alpaca PAPER es únicamente lectura de cuenta.
7. PR #6–#33 han mejorado ventanas de validación, métricas descriptivas, costes, huellas y coherencia de artefactos. No convierten datos sintéticos en evidencia económica. Ninguna mejora de IA de noticias o estrategia ML está demostrada en producción.

## Diagnóstico crítico: por qué no confiar aún en la estrategia

- **Hipótesis insuficiente:** reglas EMA/RSI/VWAP/volumen son un disparador algorítmico, no una demostración del origen económico de un alpha persistente. Muchos participantes observan señales semejantes.
- **Muestra corta y concentrada:** ~30 días y tres tecnológicas estadounidenses correlacionadas no cubren regímenes, años ni universos diversos. 812 operaciones no equivalen a 812 observaciones independientes.
- **Sesgo de ejecución:** 2 bps constantes y comisión cero no demuestran precio ejecutable, spreads efectivos ni coste de posiciones cortas. Pequeños movimientos pueden desaparecer al modelar fills realistas.
- **Sesgo de selección/sobreajuste:** modificar reglas tras observar fallos y volver a probar sobre los mismos datos puede fabricar resultados falsos. Un conjunto de prueba final intacto es obligatorio.
- **Brecha software→beneficio:** CI, paper y varias versiones de estrategia no son sustitutos de un test causal, cronológico y neto de costes. IA en noticias no corrige por sí sola una ventaja negativa.

## Decisiones y falsabilidad (criterios propuestas, no estándares de mercado)

### Puerta 0 — disponibilidad de evidencia (GO de investigación solo si pasa)

- Conseguir histórico autorizado e identificable, idealmente 12–24 meses de barras intradía que incluyan distintos entornos; **6 meses sería apenas exploratorio**. Más de tres símbolos y comprobación de cobertura, corporate actions, cambios de horario, bid/ask o proxy de spread, disponibilidad temporal real.
- Congelar copia local inmutable + SHA256 + feed/licencia + periodo + universo + ajustes + versión del código. Ejecutar CLI en Mac autorizado; no subir Parquet, tokens ni claves a GitHub.
- Reproducir o desmentir formalmente el resultado anterior de V3.1. Si el histórico original no está disponible, marcarlo NO VERIFICABLE y **no usarlo como base cuantitativa**.
- Si no se logra información suficiente y legalmente utilizable sin costes adicionales, **STOP la investigación intradía de 1 minuto con ese feed**; reconsiderar frecuencia o proyecto.

### Puerta 1 — prueba de una hipótesis congelada

- Congelar antes del test V3.1 original, parámetros, universo y modelos de ejecución; comparar con no-operar, un benchmark pasivo ajustado por exposición/riesgo y un baseline sencillo (momentum/reversión) predefinido. No probar decenas de variantes hasta encontrar una ganadora.
- Separación estrictamente temporal: entrenamiento/validación, embargo adecuado al horizonte de etiqueta y bloque final OOS **intocable**. Registrar número de decisiones probadas, operaciones, intervalos y resultados también negativos.
- Reportar expectativa neta en R, retorno neto, profit factor, max drawdown, exposición, tamaño de muestra efectivo, subperiodos y por símbolo. Incorporar spreads, slippage, comisiones/tasas aplicables, costes de SHORT y escenarios de coste base/duplicado/triplicado.
- **FAIL V3.1:** si la expectativa neta OOS es <= 0, PF <= 1, o la ventaja desaparece ante incrementos moderados de costes; si depende de un solo símbolo/periodo; si pierde frente a baselines de riesgo comparable, o si hay fuga temporal. No retocar V3.1 sobre el bloque de prueba.
- **INCONCLUSO:** punto estimado positivo pero incertidumbre amplia, intervalos compatibles con cero, pocos trades o cobertura insuficiente. No pasar a Paper; recolectar más datos sin cambiar reglas.
- **GO a revisión Paper (todavía sin orden):** resultados netos OOS robustamente positivos con incertidumbre estrecha, consistencia de distintos periodos, sensibilidad razonable a costes y mejora frente a al menos un baseline comparable. El equipo debe fijar un umbral cuantitativo antes de mirar datos, por ejemplo límite inferior del intervalo de confianza por bloques por encima de 0; no garantizarlo por regla de dedo.

### Puerta 2 — simulación prospectiva

- Solo con GO de puerta 1: verificar credenciales exclusivamente PAPER, riesgo diario, idempotencia, reconciliación, recovery, auditoría de fills y kill switch; nueva autorización para emitir **órdenes virtuales**. Nunca dinero real.
- Mantener estrategia congelada en seguimiento prospectivo por varios regímenes; tratar Paper como aproximación, no como prueba de rentabilidad LIVE. Alpaca no incluye impacto de mercado, latencia/slippage reales, cola de órdenes ni algunos costes.
- **STOP operativo:** controles fallan o ejecución diverge materialmente de los supuestos; si no aparecen oportunidades suficientes o la expectativa desaparece.

## Experimento mínimo y límite de inversión adicional

1. **Primero datos, no código:** intentar importar histórico local, validar integridad y reproducir resultados originales. Sin datos, no programar otra estrategia.
2. **Luego una sola prueba congelada:** V3.1 frente a benchmarks y coste conservador, sobre ventanas cronológicas y holdout untouched. No ML, IA de noticias, broker ni interfaz mientras falte evidencia.
3. **Decisión registrada:** STOP V3.1, PIVOT del marco temporal/universo, o GO solo para continuar investigación. Un resultado favorable no autoriza dinero real.
4. **Presupuesto inicial:** 0 USD nuevos y máximo ~10 horas de investigación humana/técnica para la auditoría de disponibilidad/reproducibilidad. Si no se dispone de suficientes datos para la prueba, marcar bloqueo y pedir una decisión explícita antes de invertir más tiempo. El límite de 10h es una política propuesta para evitar coste hundido, no una predicción de duración.

## Riesgo de oportunidad y alternativas

- **Opción A — seguir construyendo V3.1:** NO recomendada; amplia coste hundido sin acreditar alpha.
- **Opción B — reutilizar software como plataforma de investigación con un experimento limitado:** recomendada provisionalmente. El valor residual es infraestructura y aprendizaje; retorno financiero desconocido.
- **Opción C — cerrar TRADING IA como intento de generar ingresos:** opción racional si faltan datos, tiempo o no hay edge; conservar repositorio como trabajo técnico sin esperar ganancias.

## Literatura de contexto (no replica nuestro caso)

- Bailey, Borwein, López de Prado y Zhu, *The Probability of Backtest Overfitting* (2017): https://escholarship.org/uc/item/4w1110bb — riesgo al elegir estrategias tras probar muchas.
- Gu, Kelly y Xiu, *Empirical Asset Pricing via Machine Learning*, Review of Financial Studies (2020): https://doi.org/10.1093/rfs/hhaa009 — ML puede mejorar ciertas predicciones de primas de riesgo fuera de muestra; NO valida una estrategia de scalping a un minuto.
- Barber, Lee, Liu y Odean, *The Cross-Section of Speculator Skill: Evidence from Day Trading* (2014): https://www.sciencedirect.com/science/article/pii/S1386418113000190 — pocos day traders tuvieron retornos anormales positivos netos de costes en ese mercado y periodo; no extrapolar tasas mecánicamente.
- Alpaca, *Paper Trading Specification*: https://github.com/alpacahq/user-docs/blob/master/content/trading-on-alpaca/paper-trading.md — supuestos y limitaciones del paper trading.

## Conclusión y prohibiciones

**Decisión actual:** NO GO de trading (incluido paper), GO limitado para evaluar datos y una hipótesis pre-registrada, STOP al crecimiento funcional no ligado a evidencia. Sin acceso al histórico no hay resolución empírica de rentabilidad.
Se debe mantener el baseline V3.1, no modificar resultados ni declarar rendimiento, no ejecutar órdenes paper/live, no gastar ni contratar fuentes sin decisión expresa, no enviar secretos ni datos con licencia incierta a GitHub.

**Revisión siguiente:** solo cuando exista reporte real verificable de procedencia, calidad, ejecución y resultados congelados. No aumentar un porcentaje de «avance económico» por cantidad de PR.
