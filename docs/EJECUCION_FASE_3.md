# Validación offline reproducible

Usar Python 3.12, Linux/macOS y una copia autorizada del dataset. No requiere
credenciales ni conexión a Alpaca. Ningún comando siguiente envía órdenes.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest -q
```

Dependencias instaladas y verificadas: `docs/entorno_validado_fase3.txt`.
Los archivos de requisitos originales siguen siendo la fuente de instalación.

En el equipo con datos reales, conservar una copia inmutable y verificar fuente,
licencia, ajustes por splits/dividendos y semántica de timestamps. Se requieren
symbol, timestamp UTC con zona, open, high, low, close, volume; también se admite
MultiIndex symbol/timestamp. Las barras se etiquetan por apertura, cada minuto.
No usar un hash recalculado como sustituto de un identificador previamente
congelado y aprobado para el estudio.

```bash
sha256sum /ruta/autorizada/historico.parquet
# macOS: shasum -a 256 /ruta/autorizada/historico.parquet
python -m trading_ia.investigacion /ruta/autorizada/historico.parquet \
  --sha256 HASH_PREVIAMENTE_REGISTRADO \
  --salida runs/estudio-001 \
  --fuente 'Proveedor, feed, rango y versión de extracción' \
  --licencia 'Referencia a autorización local de investigación' \
  --ajustes raw
```

Seleccionar `raw`, `split` o `all` según evidencia del proveedor; declararlo no
ajusta ni verifica automáticamente los precios. Revisar corporate actions,
universo histórico y posibles sesgos de supervivencia antes de interpretar métricas.
El directorio de salida debe ser nuevo y tener espacio para una copia completa.
Se conservan snapshot, reportes original/regular, seis tablas, log y ejecución JSON.
Un fallo produce código de salida 1 y estado `error`; no interpretar archivos
parciales como resultados completos. Fallos al crear el directorio o al registrar
metadatos previos no pueden garantizar un reporte persistido.

La validación exige sesiones completas; el extendido válido se audita y excluye.
Huecos IEX legítimos también bloquean indicadores: no se imputa ninguna barra.
Saltos superiores al 50% entre observaciones consecutivas, incluidos overnight,
bloquean el ejecutor para revisión. Esto es un control de calidad conservador,
no un detector fiable de splits: cambios menores pueden pasar inadvertidos.

Repetir con el mismo SHA en `runs/estudio-002`. Comparar configuración, commit,
hashes de código, paquetes y `etapas[*].sha256_logico`; timestamps de ejecución
variarán. El hash lógico conserva orden y esquema y serializa floats con 15
cifras; no promete identidad bit a bit entre plataformas/versiones. Los hashes
Parquet permiten además verificar los bytes exactos. Conservar toda la carpeta
fuera de Git. `runs/` y todos los Parquet están ignorados; otros destinos requieren
el mismo cuidado con datos y metadatos privados.

Prueba sintética independiente, sin datos de mercado:

```bash
python tools/demo_fase3.py runs/demo-sintetico.parquet
sha256sum runs/demo-sintetico.parquet
python -m trading_ia.investigacion runs/demo-sintetico.parquet \
  --sha256 HASH_DEL_FIXTURE --salida runs/demo-001 \
  --fuente 'Fixture sintético tools/demo_fase3.py' \
  --licencia 'Datos sintéticos de prueba' --ajustes raw --sintetico
```

Los parámetros siguen V3.1: capital 100000, riesgo por operación 1%, total 3%,
tres posiciones, slippage 2 bps y comisión cero. ATR × 1.5 y objetivo nominal 2R;
EMA 9/21, Wilder 14, VWAP diario, volumen relativo de 20 barras. Las señales usan
el cierre del minuto anterior a la apertura de entrada. Los niveles de candidatos
usan la apertura siguiente como referencia de ejecución, nunca su high/low/close.
No representan una orden enviada con conocimiento anticipado de esa apertura.
Los indicadores mantienen estado entre sesiones, salvo VWAP. No se optimizan.

`backtesting_v3_1.ejecutar()` mantiene archivos y constantes configurables y devuelve
además las tres tablas. La salida textual se reduce a confirmación contable y
conteo. Para programas nuevos usar `trading_ia.backtest.simular` y `Configuracion`.
Los scripts históricos siguen ejecutándose al cargarse; usar los módulos del
paquete para importar sin efectos de E/S.
