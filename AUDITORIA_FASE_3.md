# Fase 3 — Validación integral e infraestructura de investigación

Fecha: 2026-10-16. Base obtenida con `git fetch origin main`: `deb5ce2`.
No hay datasets históricos locales en el checkout ni en shared/downloads,
library-files o scratch. Solo se ejecutaron fixtures sintéticos. No se usaron
credenciales de mercado ni se consultaron cuentas o enviaron órdenes.

## Hallazgos y correcciones

| Área | Hallazgo | Resolución o límite |
| --- | --- | --- |
| Descarga | Escritura inicial directa, susceptible de truncamiento | Temporal y reemplazo atómico en mismo directorio |
| Actualización | Se reemplazaba histórico antes de informar fallo parcial | Abortar antes del reemplazo si falla algún símbolo |
| Calidad | Vacíos, símbolos nulos y segundos distintos de cero podían pasar controles | Errores explícitos antes de indicadores |
| Calidad | Saltos overnight omitidos por filtro de continuidad | Advertencia también entre sesiones; ejecutor bloquea saltos para revisión |
| Indicadores/señales/candidatos | Fórmulas ligadas a scripts con E/S al cargar | Funciones compartidas en `trading_ia.etapas`; fórmulas y umbrales preservados |
| Candidatos | V3.1 descartaba silenciosamente timestamps de entrada inválidos | Error si no siguen exactamente 60 s o falta vela regular de señal/entrada |
| Backtest | Acoplamiento Parquet y motor | `simular` recibe copias de DataFrames y configuración inmutable, retorna tablas |
| Backtest | Ausencia de trades se confundía con fallo | Resultado vacío, curva constante si no hay posiciones |
| Reproducibilidad | Rutas y artefactos intermedios mutables | Snapshot comprobado por SHA-256, ejecución aislada, hashes de código/tablas, versiones y parámetros |
| Diagnósticos históricos | Algunos usan `datos_acciones.parquet`, otros `datos_acciones_30dias.parquet` | Nuevo flujo explícito; no se migran indiscriminadamente herramientas antiguas |
| Automatización | `motor_automatico.py` solo actualiza y calcula indicadores | No se presenta como pipeline completo; usar ejecutor offline |

La actualización sigue deduplicando solapamientos con `keep=last` para aceptar
correcciones del proveedor; no conserva un historial de revisiones. Repetir una
descarga puede cambiar datos. Congelar snapshot antes de cualquier investigación.
No se probó la API externa sin datos y acceso explícito a un proveedor; cambios en
sus adaptadores se revisaron estáticamente, sin afirmar validación de integración.

## Contabilidad, temporalidad y estrategia

Se conservan salida por gap antes de nuevas entradas, prioridad al stop en doble
toque, orden alfabético determinista entre candidatos simultáneos, restricción de
capital sin apalancamiento y límites de riesgo nominal. La suite previa verifica
LONG/SHORT, slippage, gaps con pérdida mayor que 1R, capital, simultaneidad y
cierres tempranos. No se modifican parámetros para mejorar rendimientos.

Las pruebas nuevas comprueban que alterar el futuro no cambia indicadores,
señales ni candidatos cuya entrada ya ocurrió. `shift(-1)` en candidatos obtiene
solo timestamp/apertura de ejecución; no debe usarse para filtrar señales con
información futura. El motor no decide entradas con high/low/close de ese minuto.
El modo diagnóstico no estricto todavía usa último dato disponible para cierre
y rechazo de última entrada: conoce el final observado. No es una simulación
operativa válida ante interrupciones; el ejecutor reproducible siempre es estricto.

Mantener estado de EMA/RSI/ATR entre sesiones, incluir volumen actual en VOL_REL,
y dimensionar stop/objetivo sobre apertura son definiciones de estrategia,
no errores de infraestructura. Quedan documentadas sin cambiarlas.

## Evidencia ejecutada

- Python 3.12.14, entorno virtual limpio; instalación de requisitos completada.
- `python -m pytest -q`: **56 pruebas aprobadas** (42 preexistentes y 14 nuevas).
- `python -m pip check`: sin incompatibilidades.
- Dos ejecuciones CLI completas del fixture sintético: seis hashes lógicos
  idénticos y 19 operaciones de prueba. Registro compacto en
  `docs/resultado_sintetico_fase3.json`; no son resultados históricos.
- Nuevo CI offline para repetir suite y comprobación de dependencias; ejecución
  remota pendiente de publicación y servicio CI.

Procedimiento real: `docs/EJECUCION_FASE_3.md`. Las carpetas `runs/` contienen
snapshots y resultados privados y se excluyen de Git. Solo se versiona evidencia
identificada explícitamente como sintética.

## Interfaces futuras y límites pendientes

`trading_ia.eventos.Evento` exige identidad, fuente, revisión, SHA-256 de contenido,
y timestamps con zona de publicación, recepción y disponibilidad en orden.
La consulta as-of debe excluir revisiones aún no disponibles y preservar versiones.
No existe conexión a noticias, clasificación de contenido ni decisiones automáticas.
Los timestamps declarados requieren evidencia del proveedor; el contrato no
certifica su veracidad ni detecta correcciones retrospectivas por sí solo.

Pendientes externos: dataset autorizado, corporate-action master, verificación de
ajustes y licencias, datos de universo histórico, validación histórica y walk-forward.
El control de saltos es heurístico y no sustituye reconciliar splits/dividendos.
No se modelan profundidad, spread variable, fills parciales, latencia, borrow,
margen real o participación en volumen. Sin esos datos no se afirma ejecución real
ni capacidad predictiva. Versiones anteriores del backtest permanecen históricas;
solo V3.1 y el nuevo ejecutor forman el camino validado por esta fase.

Publicación: consultar el estado final de la tarea. `gh auth status` informó token
inválido; se intenta Git por separado. No se modifican credenciales para resolverlo.

Estado de publicación comprobado: rama `phase3-integral-validation` publicada
correctamente en origin. La creación del PR en borrador con `gh pr create --draft`
falló: `Post https://api.github.com/graphql: Forbidden`. Es un bloqueo externo de
acceso a la API; el PR no se ha creado. Título y descripción revisables en
`docs/PR_FASE_3.md`. Para completarlo desde un entorno con acceso autorizado:

```bash
gh pr create --repo osmarhernandez123123-cyber/trading-ia \
  --base main --head phase3-integral-validation --draft \
  --title 'Fase 3: validación integral y pipeline reproducible offline' \
  --body-file docs/PR_FASE_3.md
```
