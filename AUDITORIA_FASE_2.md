# Fase 2 — Datos, calendario y confiabilidad

Fecha: 2026-10-16. Rama: `codex/fase-2-infraestructura`.

## Cambios realizados

- Integración de `exchange_calendars` 4.13.2 mediante los calendarios XNYS/XNAS.
- Horarios en UTC con conversión IANA a Nueva York, festivos, DST y cierres
  anticipados. Las barras se interpretan como minutos con etiqueta de apertura:
  09:30–15:59 en sesión normal y 09:30–12:59 en cierre a las 13:00.
- Clasificación de cobertura por sesión: completa, cierre anticipado completo,
  incompleta o sin datos.
- Validador OHLCV puro para columnas, timestamps, orden, duplicados, finitud,
  coherencia de high/low, precios positivos, volumen, horario regular, huecos y
  saltos configurables.
- Reporte JSON de calidad y manifiesto con SHA-256, versión, procedencia, licencia,
  esquema, símbolos, rango temporal, calendario y frecuencia.
- CLI local `validar_dataset.py`, sin credenciales ni acceso a red.
- V3.1 usa el calendario oficial y exige calidad completa por defecto antes de
  simular. Un cierre temprano legítimo genera `FIN_SESION`; un truncamiento solo
  puede examinarse en modo diagnóstico explícito.
- Política explícita de barras ausentes para IEX: ausencia ambigua, ausencia con
  cero operaciones confirmado y hueco sincronizado compatible con fallo probable
  del proveedor. Ningún caso rellena precios o crea barras.
- Puertas de calidad antes de indicadores, señales y candidatos, además de la
  validación final de V3.1.
- Validación en dos capas para indicadores: integridad de todas las filas antes
  del filtro y continuidad de la vista regular después del filtro.
- Nuevas pruebas de cuatro operaciones candidatas simultáneas, límite de tres
  posiciones, exposición, cierres tempranos y bloqueo estricto de datos parciales.

## Hallazgos y gravedad

### Alta

- Los datos históricos siguen ausentes, por lo que no se reproducen resultados
  de rendimiento ni se afirma rentabilidad.
- El flujo anterior aceptaba sesiones incompletas y podía producir métricas tras
  cerrarlas en la última observación. V3.1 ahora las bloquea por defecto.
- Antes de esta revisión final, indicadores, señales y candidatos podían generarse
  sobre un Parquet defectuoso y solo ser rechazados por V3.1. Cada etapa bloquea
  ahora la escritura de su salida si su entrada no es apta.
- El orden anterior de `indicadores.py` descartaba primero datos fuera de horario.
  Esto podía ocultar duplicados, OHLC inválido o timestamps ilegítimos presentes
  en el artefacto original. Ahora esas filas se validan antes de seleccionar la
  sesión regular.

### Media

- El filtro fijo 09:30–15:59 trataba todos los últimos minutos anteriores a las
  15:59 como datos incompletos, incluidos cierres tempranos oficiales. Se sustituyó
  por calendario de mercado.
- EMA, RSI, ATR y volumen relativo aún mantienen estado entre sesiones. Esto no
  usa futuro y puede ser una elección válida, pero debe fijarse como definición de
  estrategia antes de decidir si se reinicia. Los huecos intradía ya son bloqueados
  por la validación estricta y no deben llegar al cálculo de indicadores.
- XNAS es un alias de horario de XNYS en la biblioteca instalada. Para AAPL, MSFT
  y NVDA los horarios regulares y festivos relevantes coinciden; no se modelan
  reglas específicas de subastas ni sesiones extendidas.
- IEX cubre una parte del mercado y sus barras se basan en trades IEX. Un minuto
  ausente aislado no identifica su causa. En modo IEX se reporta como ambiguo;
  aun así se bloquean indicadores continuos para evitar puentear el hueco.

### Baja

- Los saltos de precio superiores al umbral son advertencias, no errores, porque
  pueden ser reales o reflejar corporate actions. Requieren revisión humana y
  datos ajustados claramente identificados.

## Riesgo de anticipación

No se añadió información futura a las señales. El calendario se conoce antes de
la sesión. V3.1 sigue entrando en la apertura posterior a la señal. La selección
conservadora de stop cuando una vela toca stop y objetivo permanece explícita.
La detección de que una sesión está incompleta se usa para impedir el backtest
estricto, no para decidir entradas rentables.

## Flujo de validación

1. Descarga/actualización: estructura, duplicados y coherencia OHLCV antes de
   reemplazar el archivo local; horario extendido solo con política explícita.
2. Integridad original: todas las filas se comprueban antes de filtrar. Se permite
   04:00–20:00 NY en días bursátiles cuando la fuente declara datos extendidos.
3. Normalización regular: se excluye el extendido legítimo y se vuelve a exigir
   cobertura completa antes de cualquier indicador.
4. Señales y candidatos: revalidación defensiva de cada artefacto intermedio.
5. V3.1: validación estricta final antes de simular.

Los controles son redundantes deliberadamente: también bloquean artefactos
intermedios antiguos o modificados fuera del pipeline.

## Pruebas

Ejecutar:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pip check
```

La suite utiliza únicamente datos sintéticos y no necesita Alpaca, cuentas ni
credenciales. Cubre festivos, cierre temprano completo/truncado, DST, paridad de
horarios XNYS/XNAS, calidad OHLCV, hashes, manifiestos, LONG/SHORT, gaps, doble
toque, slippage, riesgo, capital, simultaneidad y cierres de sesión.
También verifica ausencia IEX ambigua, cero trades con evidencia externa, hueco
sincronizado de proveedor probable y que ninguna etapa temprana escriba salida
cuando el input contiene un hueco.
Las regresiones finales añaden extendido legítimo, duplicado/ohlc inválido en
premarket, fin de semana, hora no permitida y rechazo del backtest estricto antes
de producir resultados.

## Limitaciones pendientes

- Sin dataset autorizado e inmutable no puede verificarse la historia real.
- No se detectan automáticamente splits, dividendos, cambios de símbolo, halts o
  correcciones posteriores del proveedor; deben registrarse en procedencia.
- El calendario no sustituye controles de calidad del feed ni garantiza que una
  vela presente sea correcta.
- Sigue pendiente decidir si una versión futura calculará indicadores por
  segmentos con calentamiento después de ausencias legítimas. Hasta entonces se
  bloquea la sesión, sin imputación.
- El motor mantiene las limitaciones de spread fijo, ausencia de profundidad,
  fills parciales, latencia, borrow, margen y participación en volumen.
- Falta separar completamente V3.1 en motor puro y adaptador Parquet; esta fase
  conserva su interfaz para evitar una migración amplia sin fixtures históricos.

## Próximos pasos recomendados

1. Obtener datos con derechos confirmados y congelar artefacto, manifiesto y
   reporte antes de calcular indicadores.
2. Añadir corporate-action master y política explícita adjusted/unadjusted.
3. Ejecutar regresión sobre un pequeño dataset autorizado y versionado fuera de
   Git, comparando hashes y resultados deterministas.
4. Modularizar el motor y preparar validación walk-forward cronológica.
