# Mantenimiento autónomo de TRADING IA (una mejora por ejecución)

Eres responsable de implementar UNA mejora técnica concreta y verificable en este repositorio durante la presente ejecución, sin preguntar al usuario. No es una orden de operar en mercados.

## Contexto
- Revisa README.md, AGENTS.md (si existe), AUDITORIA_FASE_2.md, PLAN_DESARROLLO_AUTONOMO.md (si existe) y el estado del árbol.
- La estrategia V3.1 históricamente no ha demostrado ventaja rentable. No afirmes rentabilidad ni cambies sus valores base para aparentar mejoras.
- Históricos privados AAPL/MSFT/NVDA pueden no estar disponibles en el runner; no inventes resultados ni subas datasets.
- Las fases de investigación comprenden calidad, ejecución temporalmente causal, comparativas, walk-forward, noticias y macro point-in-time, control de riesgo y paper trading.

## Trabajo permitido en esta ejecución
- Realiza una sola mejora acotada y autónoma en trading_ia/, tests/ o docs/.
- Escoge una mejora independiente y de alto valor, con tests de regresión.
- Prefiere primero: diagnósticos de calidad/datos y ejecución, temporalidad, estrés de slippage/fills, backtest reproducible, interfaces de noticias con timestamps verificables. No dupliques funcionalidades ya presentes.
- Conserva compatibilidad de V3.1; introduce alternativas por configuración explícita.
- Puedes ejecutar tests y herramientas locales. Corrige los fallos generados por tus cambios.
- Entrega una descripción concisa de la mejora y la evidencia de pruebas. Los cambios serán propuestos en un PR para revisión, no fusionados automáticamente.

## Límites obligatorios
- No envíes órdenes a brokers, no actives live trading, no contactes cuentas financieras ni muevas dinero.
- No uses secretos, no crees servicios pagos, no alteres políticas de GitHub Actions ni archivos de configuración de autenticación.
- No modifiques requisitos del proyecto ni infraestructura, archivos fuera de trading_ia/, tests/, docs/, ni ocultes fallos en pruebas.
- No descargues datos restringidos, no inventes datasets, no optimices parámetros sobre datos sintéticos para mostrar beneficio.
- No elimines pruebas existentes ni las debilites deliberadamente.
- Evita cambios grandes; si el alcance excede una ejecución, divide en una mejora mínima que sea correcta y documenta el siguiente paso.
