# TRADING IA

Proyecto experimental de análisis y backtesting de acciones estadounidenses
(inicialmente AAPL, MSFT y NVDA) con Python y datos de Alpaca.
Los resultados históricos son preliminares y no demuestran rentabilidad.
No constituye asesoramiento financiero. No se autoriza operar con dinero real.
El envío de órdenes, incluidas las de paper trading, requiere autorización explícita.

## Instalación

Entorno de referencia: Python 3.12.10 en macOS. Para los scripts que utilizan
`fcntl`, se necesita macOS o Linux.

```bash
git clone https://github.com/osmarhernandez123123-cyber/trading-ia.git
cd trading-ia
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

El repositorio es privado y requiere acceso autorizado a GitHub.
Las versiones de dependencias proceden del entorno local existente.
Su instalación en un venv limpio Linux/Python 3.12 se validó en Fase 3;
`requirements-lock.txt` fija restricciones transitivas sin hashes.

## Configuración y datos

Para acceder a Alpaca, copiar `.env.example` a `.env` y completar las claves
únicamente en el entorno local. No incluir credenciales en código, commits o logs.
El análisis de datos históricos ya disponibles no necesita conectarse a Alpaca.

Los archivos Parquet se excluyen del repositorio porque su licencia de
redistribución no está confirmada. Los backtests necesitan datos locales
compatibles; el repositorio por sí solo no reproduce los resultados históricos.
Mantener una copia inmutable del histórico utilizado y conservar la separación
cronológica entre entrenamiento y prueba, sin seleccionar parámetros con esta última.

## Componentes

- `datos_mercado.py` y `actualizar_datos.py`: descarga y actualización de datos.
- `indicadores.py`, `motor_analisis.py` y `preparar_entradas.py`: indicadores,
  señales y entradas candidatas.
- `backtesting*.py`: versiones históricas del backtest.
- `dividir_datos.py`, `diagnostico*.py` y `auditar*.py`: separación y diagnósticos.

## Pruebas

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Las pruebas sintéticas de V3.1 cubren LONG/SHORT, stop, objetivo, gaps,
slippage, doble toque intrabar, datos OHLC inválidos, dimensionamiento, capital
y cierre de sesión. Véase `AUDITORIA_FASE_1.md` para alcance y limitaciones.

## Calidad y trazabilidad de datos

Antes de ejecutar V3.1, validar cada artefacto histórico y conservar su reporte y
manifiesto junto al dataset local (los Parquet siguen excluidos de Git):

```bash
python validar_dataset.py datos_acciones_30dias.parquet \
  --reporte artefactos/calidad.json \
  --manifiesto artefactos/manifiesto.json \
  --dataset-id acciones-iex-1m \
  --version 2026.10.1 \
  --fuente "Alpaca IEX" \
  --licencia "Describir autorización aplicable" \
  --calendario XNYS \
  --politica-huecos estricta \
  --politica-sesion extendido-permitido
```

El comando termina con código 2 si encuentra errores. Registra SHA-256, versión,
procedencia, licencia, esquema, símbolos y rango UTC, pero nunca copia el dataset.
Los archivos JSON generados deben revisarse antes de decidir si se versionan: no
deben contener rutas privadas ni información contractual sensible.

Alpaca IEX no garantiza necesariamente una barra por símbolo y minuto: las barras
se basan en trades IEX y ese feed cubre solo una parte del mercado. La política
completa para ausencias, evidencia de cero transacciones y fallos sincronizados
está en `POLITICA_HUECOS.md`. Ningún modo fabrica barras o rellena precios.

La política de sesión es independiente de la estrategia. `solo-regular` rechaza
cualquier fila fuera de la sesión oficial. `extendido-permitido` acepta únicamente
04:00–20:00 America/New_York en fechas bursátiles válidas; las filas aceptadas se
auditan como `HORARIO_EXTENDIDO_PERMITIDO`, pero se excluyen antes de calcular los
indicadores. Festivos, fines de semana, horas fuera de esa ventana, duplicados y
OHLCV inválido siempre son errores.

`backtesting_v3_1.py` exige por defecto sesiones completas según el calendario
oficial. Reconoce festivos, DST y cierres anticipados. El modo no estricto existe
solo como argumento de Python (`ejecutar(exigir_calidad=False)`) para diagnósticos
controlados de datos truncados; no debe usarse para publicar métricas.

La validación no ocurre solo en el backtest. `datos_mercado.py` y
`actualizar_datos.py` comprueban OHLCV antes de guardar; `indicadores.py`,
`motor_analisis.py` y `preparar_entradas.py` vuelven a exigir continuidad antes
de producir el siguiente artefacto. Así, un archivo defectuoso no puede generar
indicadores, señales o candidatos y ser rechazado recién al final.

En `indicadores.py` la validación del artefacto original ocurre antes del filtrado
horario. Después del filtrado se ejecuta una segunda validación, específica para
la continuidad minuto a minuto de la vista regular usada por la estrategia.

Varios scripts ejecutan acciones al cargarse. No importarlos como comprobación
de instalación. Revisar cada script antes de ejecutarlo desde la raíz del proyecto:
puede consultar servicios externos o sobrescribir datos y resultados locales.
`main.py` consulta la cuenta de Alpaca paper; no es un punto de entrada al backtest.

La contabilidad de ejecución, slippage y cálculo de R tienen regresiones sintéticas;
su validación histórica real sigue pendiente.
No activar actualizaciones automáticas ni envío de órdenes durante la preparación
del entorno de desarrollo.

## Investigación reproducible — Fase 3

Usar `python -m trading_ia.investigacion --help` para ejecutar desde un Parquet
local identificado por SHA-256, en un directorio nuevo, sin credenciales.
Procedimiento, contratos para eventos, hallazgos y limitaciones en
[AUDITORIA_FASE_3.md](AUDITORIA_FASE_3.md).
El motor `trading_ia.backtest.simular` opera en memoria; el adaptador V3.1 conserva
su interfaz. Un resultado sin operaciones es válido y conserva la curva de capital.
