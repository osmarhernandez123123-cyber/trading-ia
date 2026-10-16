# Política de barras ausentes

## Evidencia del proveedor

La documentación publicada por Alpaca indica que IEX representa aproximadamente
el 2,5 % del volumen de mercado estadounidense y que sus barras de minuto se
construyen a partir de operaciones de IEX:

- [Stock pricing data](https://github.com/alpacahq/alpaca-docs/blob/master/content/api-references/market-data-api/stock-pricing-data/_index.md)
- [Real-time stock data](https://github.com/alpacahq/alpaca-docs/blob/master/content/api-references/market-data-api/stock-pricing-data/realtime.md)

Por tanto, la ausencia de una barra IEX no demuestra por sí sola un error. Puede
no haber existido una operación elegible en ese mercado durante el minuto, o
puede faltar información por un problema de obtención/proveedor. Una serie de
barras no permite distinguir causalmente ambos casos.

## Reglas

| Situación observable | Clasificación | Calidad del feed | Indicadores continuos |
| --- | --- | --- | --- |
| Todos los minutos oficiales presentes | Completa | Aceptada | Permitidos |
| Minuto ausente, sin evidencia adicional | `BARRA_AUSENTE_AMBIGUA` | Advertencia en política IEX | Bloqueados |
| Ausencia respaldada por trades/auditoría del mismo feed | `SIN_TRANSACCIONES_CONFIRMADO` | Advertencia | Bloqueados |
| Mismo minuto ausente en una fracción configurable de varios símbolos | `HUECO_PROVEEDOR_PROBABLE` | Error | Bloqueados |
| Cualquier ausencia en política estricta | `HUECOS_DE_SESION` | Error | Bloqueados |

La sincronía se considera indicio, no prueba causal. Por defecto requiere al menos
dos símbolos y el 67 % del universo observado. Ambos umbrales pertenecen a
`PoliticaHuecos` y pueden configurarse explícitamente.

## Decisiones conservadoras

- Nunca crear barras para minutos ausentes.
- Nunca hacer forward-fill de OHLC, volumen o indicadores.
- Una barra de volumen cero no representa automáticamente un minuto sin trades;
  se conserva como anomalía a revisar.
- Confirmar “sin transacciones” requiere evidencia externa por símbolo y minuto,
  procedente del mismo feed y conservada con el manifiesto del dataset.
- Incluso una ausencia legítima rompe la serie regular de un minuto. Hasta que se
  diseñe y valide un cálculo segmentado con calentamiento posterior al hueco, no
  se permiten indicadores ni señales sobre esa sesión.

## Modos configurables

`estricta` es el modo por defecto para métricas publicables: toda ausencia es
error. `iex-conservadora` evita etiquetar una ausencia aislada como corrupción
sin evidencia, pero no la convierte en dato apto para indicadores.

```bash
python validar_dataset.py datos.parquet \
  --reporte calidad.json --manifiesto manifiesto.json \
  --dataset-id acciones-iex-1m --version 1 \
  --fuente "Alpaca IEX" --licencia "..." \
  --politica-huecos iex-conservadora
```

El comando devuelve código 2 tanto para errores como para datasets que no son
aptos para indicadores continuos.

## Horario extendido e integridad original

La política de huecos no debe confundirse con la política de sesión. El dataset
original se valida antes de eliminar filas:

- `solo_regular`: solo permite minutos de la sesión oficial.
- `extendido_permitido`: permite 04:00–20:00 Nueva York, exclusivamente en una
  fecha de sesión reconocida por el calendario.

El horario extendido válido se registra como información, no como error. Aun así,
no participa en EMA, RSI, ATR, VWAP, volumen relativo, señales ni backtesting. Un
registro de fin de semana/festivo, fuera de la ventana configurada, duplicado o
con OHLCV inválido bloquea el pipeline antes de que el filtro pueda ocultarlo.
