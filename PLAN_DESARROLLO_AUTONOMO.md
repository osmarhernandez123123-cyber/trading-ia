# TRADING IA — desarrollo autónomo y definición de terminado

Este documento es el backlog operativo. Las iteraciones deben identificar
primero el estado real de GitHub, CI, pruebas y datos autorizados. No se presupone
que un bot o modelo de IA sea rentable por estar programado.

## Estado base

- Fases 1, 2 y 3 integradas en main (PR #3 fusionado el 23/10/2026):
  motor V3.1 separado, pipeline reproducible, modelos de ejecución diferida,
  pruebas sintéticas y workflow CI. No se afirma rentabilidad.
- Alpaca PAPER: solo lector seguro de cuenta integrado en main (PR #5).
  No existe acceso remoto a credenciales paper ni envío de órdenes.
- Laboratorio cuantitativo: generador de ventanas walk-forward con embargo
  por horizonte de etiqueta y tests, integrado en main (PR #6). Aún no
  entrena ni valida estrategias con datos reales.
- La evidencia histórica de V3.1 sigue siendo negativa. La fuente IEX puede
  ser dispersa y está sometida a controles de cobertura. Ninguna métrica
  sintética prueba rentabilidad.
- Reporte de cobertura local por símbolo/sesión (PR #7) integrado en main:
  distingue minutos presentes y ausentes, sin publicar precios ni rutas.
- Verificación de SHA-256 de archivo local (PR #8) integrada en main:
  registra huella y tamaño, compara --sha256-esperado antes de analizar y
  evita que --salida sobrescriba el dataset. Un hash no acredita procedencia,
  integridad temporal entre lecturas ni licencia de redistribución.
- Histórico AAPL/MSFT/NVDA guardado en el Mac del usuario, no accesible desde
  Codex Cloud por defecto. No se debe fingir su disponibilidad.

## Orden de trabajo autónomo

### P0 — Integridad temporal, ejecución, CI
- Validar modelo V3.1 de referencia frente a modelo con niveles fijados al
  cierre de señal y ejecución diferida, ambos claramente identificados.
- Cubrir gaps, barras ausentes, cierres anticipados, prioridad temporal,
  fills, slippage, contabilidad, datos duplicados y determinismo.
- Mantener Python 3.12, instalación limpia y validación GitHub Actions.
- PR #3 integrado tras validación automatizada. Pendientes: auditorías
  adicionales de integridad, evidencia con datasets reales autorizados y
  confirmación de ejecución reproducible en el entorno del usuario.

### P1 — Datos reales y reproducibilidad
- Diseñar una herramienta de importación local segura desde Parquet/CSV;
  nunca subir precios con redistribución no autorizada ni claves.
- Reporte de cobertura por símbolo/sesión/proveedor: implementado con
  datos locales y pruebas sintéticas (PR #7). Falta evaluar cobertura con
  históricos autorizados, diferenciar IEX disperso de fallos de proveedor
  con evidencia de fuentes y revisar límites de calidad.
- SHA-256 local, tamaño y --sha256-esperado con protección de sobrescritura
  integrados (PR #8). Pendiente: manifiesto de procedencia/versiones con
  metadatos verificables, controles contra cambios del archivo entre hash
  y lectura y política de publicación/retención de resultados.
- Identificar splits/dividendos/delistings, horario y universo histórico,
  respetando disponibilidad point-in-time.
- Ejecutar baseline con histórico autorizado cuando se encuentre accesible.
  Si no lo está, marcar bloqueo externo, seguir con módulos independientes.

### P2 — Laboratorio cuantitativo
- API común para baselines y estrategias candidatas, sin cambiar silenciosamente V3.1.
- Comparativas de LONG/SHORT/NO TRADE, costes, regímenes de mercado,
  ablation tests y errores de ejecución.
- Existe un generador de ventanas temporales con embargo y pruebas
  sintéticas (PR #6). Integrarlo después con estrategias y sus etiquetas.
- Conjuntos de entrenamiento, validación y prueba final, walk-forward,
  evitando leakage y optimización sobre el bloque de prueba.
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
