# Evidencia de validación — Fase 3

Validación local de 2026-10-16, Linux, Python 3.12. Entorno virtual limpio,
instalación de `requirements-dev.txt` con restricciones existentes.

```text
python -m pytest -q --junitxml=work/pruebas.xml
57 passed, 1 warning in 11.81s
python -m pip check
No broken requirements found.
python -m compileall -q trading_ia tests backtesting_v3_1.py
Exit 0
git diff --check
Exit 0
python -m trading_ia.investigacion --help
Exit 0
```

La advertencia procede de `websockets.legacy` al importar el SDK de Alpaca en la
prueba con proveedor simulado; es una deprecación transitiva, no un fallo del motor.
No se silencia ni se cambia la versión del SDK sin necesidad.

Las 42 pruebas anteriores siguen pasando. Las 15 nuevas cubren:
resultado vacío, capital insuficiente, no mutación, determinismo, candidatos
huérfanos/no contiguos, prefijos de indicadores/señales sin futuro, candidato sin
usar high/low/close futuros, pipeline local identificado por hash, rechazo de
hash incorrecto y salida existente, timestamps de eventos, salto entre sesiones,
símbolo nulo/vacío, dataset vacío, duplicados antes de producir artefactos,
pipeline con operaciones comparado entre dos ejecuciones y actualización fallida
con snapshot intacto. Algunos casos se agrupan en una misma prueba.

La prueba con operaciones usa exclusivamente una onda sintética:
`precio = 100 + 0.015*x + 0.3*sin(x/4)`, OHLC con rango ±0.1,
`volume = 1000 + (x % 30)*100`, sesión XNYS 2026-01-05 y símbolo TEST.
No representa un activo ni rendimiento histórico. La suite genera los archivos
solo en directorios temporales de pytest y compara todas las tablas exactamente.

Para repetir la evidencia ejecutar los comandos anteriores desde la raíz, después
de instalar las dependencias. El JUnit completo se conserva como entrega local;
no se incluyen datasets ni Parquet en la rama.

No hubo pruebas con históricos reales: no se encontraron datasets autorizados.
No se ejecutó el workflow remoto ni se activaron operaciones o descargas.

## Revisión de ejecución — 2026-10-17

Suite ampliada: **91 passed, 1 warning in 25.59s**. Se conservan las 57 pruebas
anteriores, seis pruebas remotas del modelo por velas y 28 casos nuevos
para temporalidad y ejecución por cotizaciones.
`pip check`, `compileall` y `git diff --check`: correctos. Resultados económicos V3.1 sin diferencias respecto a la referencia `411f842`;
se integra el campo remoto optativo `LATENCIA_VELAS`, con cero por defecto. Comparación completa repetida dos veces con igualdad exacta.
Advertencia transitiva `websockets.legacy` sin cambios.

Informe y comandos en [docs/REVISION_EJECUCION_PR3.md](docs/REVISION_EJECUCION_PR3.md);
resultados sintéticos detallados en
[docs/COMPARACION_EJECUCION_SINTETICA.json](docs/COMPARACION_EJECUCION_SINTETICA.json).
Los resultados sintéticos no demuestran rentabilidad ni realizabilidad de fills.
