# TRADING IA — desarrollo autónomo y definición de terminado

Este documento es el backlog operativo. Las iteraciones deben identificar
primero el estado real de GitHub, CI, pruebas y datos autorizados. No se presupone
que un bot o modelo de IA sea rentable por estar programado.

## Estado base

- Fases 1 y 2 integradas en main.
- Fase 3: motor V3.1 separado y pipeline reproducible, PR #3. La evidencia
  histórica de la estrategia sigue siendo negativa; las pruebas de Fase 3
  son sintéticas. La fuente IEX puede ser dispersa y está sometida a controles
  de cobertura. Ninguna métrica sintética prueba rentabilidad.
- Histórico AAPL/MSFT/NVDA guardado en el Mac del usuario, no accesible desde
  Codex Cloud por defecto. No se debe fingir su disponibilidad.

## Orden de trabajo autónomo

### P0 — Integridad temporal, ejecución, CI
- Validar modelo V3.1 de referencia frente a modelo con niveles fijados al
  cierre de señal y ejecución diferida, ambos claramente identificados.
- Cubrir gaps, barras ausentes, cierres anticipados, prioridad temporal,
  fills, slippage, contabilidad, datos duplicados y determinismo.
- Mantener Python 3.12, instalación limpia y validación GitHub Actions.
- Consolidar el PR #3 solo con pruebas correctas y revisión de cambios.

### P1 — Datos reales y reproducibilidad
- Diseñar una herramienta de importación local segura desde Parquet/CSV;
  nunca subir precios con redistribución no autorizada ni claves.
- Crear un reporte de cobertura por símbolo/sesión/proveedor y diagnóstico
  explícito de barras ausentes (IEX disperso vs fallo de proveedor).
- Identificar splits/dividendos/delistings, horario y universo histórico,
  respetando disponibilidad point-in-time.
- Ejecutar baseline con histórico autorizado cuando se encuentre accesible.
  Si no lo está, marcar bloqueo externo, seguir con módulos independientes.

### P2 — Laboratorio cuantitativo
- API común para baselines y estrategias candidatas, sin cambiar silenciosamente V3.1.
- Comparativas de LONG/SHORT/NO TRADE, costes, regímenes de mercado,
  ablation tests y errores de ejecución.
- Conjuntos temporales de entrenamiento, validación y prueba final,
  walk-forward con embargo cuando corresponda, evitar leakage y optimización
  sobre test.
- Informar tamaño muestral, incertidumbre, drawdown, retorno,
  expectativa, exposición y fallos; no esconder resultados negativos.

### P3 — Investigación de noticias, macro y datos fundamentales
- Ingesta autorizada/licenciada y cache histórico de eventos con hashes,
  timestamps ocurrido/publicado/recibido, revisiones inmutables e identificador.
- Joins point-in-time, mapping de símbolos y pruebas ante publicaciones tardías.
- Primero usar fixtures sintéticos y replay; no asegurar que la IA
  predice mercados. Separar observación, extracción y señales.

### P4 — Motor multifactorial y gestión del riesgo
- Agregar explicaciones y scoring, filtros de liquidez/volatilidad,
  límites de concentración, capital y pérdida diaria, apagado de emergencia.
- Tests de estrés y manejo de eventos adversos, spreads y fills adversos.
- Mantener capacidad NO TRADE; nunca forzar una señal.

### P5 — Paper trading y operaciones
- Interfaz broker aislada, con modo SIMULACIÓN por defecto.
- Paper execution sólo tras controles de credenciales, idempotencia,
  reconcile de órdenes/posiciones, errores, reconexión, alertas y kill switch.
- Verificación prolongada de métricas paper netas de costes,
  diferencias entre fills paper y supuestos de backtest.

### P6 — Producto terminado
- CLI y manual de instalación para el usuario, ejemplos de uso,
  configuración segura, logs, pruebas CI reproducibles y runbook.
- Panel o reporte claro de señales, riesgo, datos, experimentos y resultados.
- Cobertura de tests de componentes y end-to-end en modo sintético/paper.
- Entrega final: qué hace, qué no hace, evidencia verificada y bloqueos.

## Condiciones de operación y autonomía

Se autoriza desarrollar y corregir código, crear ramas, commits, pruebas,
documentación, Issues y PRs, revisar CI y fusionar cambios de investigación
no financieros cuando las comprobaciones sean satisfactorias y no se
introduzcan acciones externas de riesgo. Conservar historial auditable.

**No** ejecutar órdenes reales ni usar fondos, contratar servicios, revelar
secretos, desactivar controles de calidad, publicar datos privados, mentir
sobre rentabilidad o habilitar live trading sin una nueva decisión expresa
del usuario. Las credenciales conectadas no autorizan cualquier uso.

## Criterio de calidad

- No modificar simultáneamente el baseline V3.1 para acomodar resultados.
- Una prueba sintética demuestra funcionamiento, no oportunidad económica.
- Todas las variaciones de la estrategia se etiquetan por versión/dataset.
- Ningún PR crítico se fusiona con CI fallida o sin examinar el diff.
- Un bloqueo externo se documenta y no paraliza trabajo independiente.

## Continuidad

La tarea programada de ChatGPT puede revisar GitHub periódicamente y efectuar
ediciones si sus herramientas están disponibles. GitHub Actions valida commits
cuando corresponde. Codex Cloud no queda automáticamente iniciado por un
comentario, un plan, una tarea de ChatGPT ni una modificación en GitHub.
