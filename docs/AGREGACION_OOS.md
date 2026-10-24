# Agregación OOS multi-ventana (investigación, sin broker)

`trading_ia.agregacion_oos.agregar_pruebas(ventanas, operaciones_por_ventana)`
recibe una secuencia cronológica de `VentanaTemporal` y un DataFrame de
operaciones cerradas por cada bloque de prueba correspondiente. Todos los datos
pueden ser sintéticos. No consulta mercado, no lee credenciales y no envía órdenes.

## Controles

- Reutiliza `evaluar_prueba` para validar fechas explícitas, R, PnL,
  riesgos, operaciones intradía y pertenencia a la ventana OOS.
- Rechaza ventanas vacías, repetidas, solapadas, desordenadas y fechas
  duplicadas, además de operaciones repetidas.
- Suma **PnL realizado** de las operaciones tal como lo reporta el backtest,
  pero **no** suma porcentajes de retorno, no compone capital ni presenta un
  drawdown combinado: las curvas individuales reinician capital.
- Calcula media R ponderada por número de operaciones, no media simple
  entre ventanas. Devuelve número de ventanas con y sin operaciones.
- Rechaza PnL sumado o expectativa R ponderada no finitos por overflow
  **entre ventanas**, incluso si cada bloque individual pasó validación.
- Añade un intervalo Wilson nominal del 95 % para la proporción de
  operaciones ganadoras; **no** es una inferencia fiable cuando existen
  correlaciones temporales, dependencia entre símbolos o selección de modelos.
  El tamaño muestral se presenta explícitamente y con n=0 el intervalo es null.

## Límites de interpretación

Una tasa de acierto elevada puede coexistir con PnL negativo. Las métricas
descriptivas no prueban un edge; no se ha validado una estrategia con históricos
reales autorizados. Los costes deben haberse modelado previamente en el PnL de
cada operación. No mezclar versiones, parámetros, mercados o políticas de
costes entre ventanas sin etiquetarlos. Mantener V3.1 sin modificaciones.

Para una evaluación de rentabilidad de cartera con reinversión, riesgo y
drawdown mark-to-market es necesario un simulador continuo fuera de muestra,
que no se implementa aquí.
