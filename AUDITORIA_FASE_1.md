# Auditoría técnica — Fase 1

Fecha: 2026-10-15. Rama de trabajo: `codex/fase-1-auditoria`.

## Alcance y evidencia disponible

Se revisaron los 18 scripts Python, `README.md` y los archivos de dependencias.
El repositorio no incluye los Parquet históricos, por lo que no fue posible
reproducir las 812 operaciones ni las métricas históricas proporcionadas. Esas
cifras se consideran antecedentes, no resultados verificados en esta auditoría.

Entorno comprobado: Python 3.12.14. Las dependencias fijadas en
`requirements.txt` se instalaron en un entorno limpio y `pip check` terminó sin
conflictos. El lock sigue sin hashes, por lo que no es plenamente reproducible
frente a sustitución de artefactos.

## Flujo del sistema

1. `datos_mercado.py`/`actualizar_datos.py` obtienen velas IEX de Alpaca.
2. `indicadores.py` filtra 09:30–15:59 America/New_York y calcula EMA, RSI,
   ATR, VWAP diario y volumen relativo.
3. `motor_analisis.py` produce LONG, SHORT o NO TRADE usando exclusivamente la
   vela ya cerrada.
4. `preparar_entradas.py` desplaza la ejecución a la apertura de la siguiente
   vela y exige continuidad exacta de 60 segundos.
5. `backtesting_v3_1.py` es el motor vigente. V1–V3 son implementaciones
   históricas y no deben usarse para resultados nuevos.

No se encontró anticipación directa en la ruta vigente: los indicadores usan
datos presentes/pasados y la entrada se ejecuta en la vela posterior a la señal.
El uso de `high`/`low` de la vela de entrada ocurre después de abrir la posición.

## Hallazgos

### Altos

- **Resultados históricos no reproducibles.** Faltan los datos fuente, su hash,
  calendario, versión del feed y artefactos de ejecución. No puede validarse la
  rentabilidad, el drawdown ni las 812 operaciones.
- **Calendario de mercado incompleto.** El filtro horario maneja DST mediante
  `America/New_York`, pero no valida festivos ni cierres anticipados oficiales.
  El motor cierra en la última observación y la etiqueta como sesión incompleta;
  no puede distinguir un cierre temprano legítimo de pérdida de datos.

### Medios

- **2R nominal no equivale a 2R ejecutable.** `preparar_entradas.py` fija SL/TP
  desde la apertura nominal. V3.1 aplica slippage adverso a entrada y salida; por
  tanto aumenta la pérdida presupuestada al stop y reduce la ganancia al target.
  No es evidencia de una salida incorrecta. Se añadieron
  `R_objetivo_nominal` y `R_objetivo_ejecutable` por operación para hacer
  auditable la diferencia. Una prueba sintética confirma 2R nominal y menos de
  2R ejecutable, coincidiendo el R realizado con este último cuando toca TP.
- **Ambigüedad intrabar inevitable con OHLC.** Si SL y TP aparecen dentro de la
  misma vela no puede conocerse el orden. V3.1 elige stop primero, una hipótesis
  conservadora correctamente probada y documentada.
- **Modelo de ejecución limitado.** No modela spread variable, liquidez,
  participación en volumen, fills parciales, latencia, halts, borrow/locate,
  margen, dividendos ni corporate actions. Un slippage fijo de 2 bps no puede
  considerarse evidencia de ejecutabilidad real.
- **Indicadores atraviesan discontinuidades.** EMA, RSI, ATR y volumen relativo
  continúan entre sesiones y después de huecos de datos. La señal exige solo que
  la vela inmediatamente anterior esté a 60 segundos; después de una vela de
  calentamiento puede reutilizar estado anterior al hueco. No se cambió porque
  decidir si se reinician por sesión es una definición de estrategia, no una
  corrección puramente técnica.
- **Scripts con efectos al importar.** Salvo V3.1, la mayoría lee/escribe datos o
  accede a red al importarse. Esto dificulta pruebas unitarias y reutilización.

### Bajos

- Coexisten cuatro motores de backtest, con riesgo de ejecutar accidentalmente
  una versión obsoleta.
- El lock de producción mezcla dependencias directas y transitivas y no incluye
  hashes; pytest quedó separado en `requirements-dev.txt`.
- V3.1 usa acciones enteras y reserva nocional sin apalancamiento. Es una
  restricción conservadora, no una réplica del margen de un bróker.

## Contabilidad y riesgo verificados sintéticamente

- Entrada a la apertura posterior a la señal.
- LONG y SHORT con stop y target.
- Slippage adverso en ambos lados.
- Gap de stop ejecutado en la apertura, permitiendo correctamente pérdidas
  superiores a 1R presupuestado.
- Doble toque resuelto a favor del stop.
- Tamaño entero limitado por 1% del patrimonio y exposición simultánea del 3%.
- Identidad entre capital final y capital inicial más PnL realizado.
- Cierre en última observación de una sesión incompleta.
- Rechazo de OHLC ausente, infinito o no positivo.

Comando: `.venv/bin/python -m pytest -q`. Resultado: **12 passed**.

## Confiabilidad actual

**Adecuado para pruebas de ingeniería con datos sintéticos; no validado para
inferencias de rendimiento ni para operar.** La mecánica principal de V3.1 tiene
cobertura sobre los casos críticos solicitados y sus invariantes contables
internas son coherentes. La ausencia del histórico y las limitaciones del modelo
de ejecución impiden calificar el backtest como validación estadística.

## Arquitectura recomendada

Separar un paquete sin efectos laterales (`trading_ia/`) con módulos `data`,
`calendar`, `indicators`, `signals`, `execution`, `portfolio` y `metrics`; dejar
los comandos de descarga/backtest en `cli/`; versionar configuración y manifiesto
de datos; mantener `tests/unit` y `tests/integration`. Migrar primero V3.1 a una
función pura que reciba DataFrames y configuración, preservando fixtures de
regresión antes de retirar V1–V3.

## Próximos pasos

1. Obtener un histórico con derechos confirmados, conservarlo inmutable y
   registrar hash, feed, zona horaria, universo y rango exacto.
2. Integrar un calendario bursátil oficial y políticas explícitas para huecos,
   cierres anticipados, halts y datos incompletos.
3. Ejecutar validación walk-forward con ventanas cronológicas, conjunto final
   bloqueado y parámetros elegidos solo en entrenamiento.
4. Añadir spread/volumen/latencia y análisis de sensibilidad de costes; reportar
   intervalos de confianza, distribución de drawdowns y estabilidad por régimen.
5. Solo después, diseñar paper trading con reconciliación de fills y controles de
   riesgo independientes; no se implementó ninguna conexión u orden en esta fase.
