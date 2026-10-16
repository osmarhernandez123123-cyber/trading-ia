# Fase 3 — Validación integral

Fecha: 2026-10-16. Base verificada mediante GitHub y `git fetch`:
`deb5ce25ec5fab23a4bb80e21f430b1d44a4e1fc` (main, fases 1 y 2 fusionadas).
No se ejecutó ningún script de cuenta, descarga o envío de órdenes.

## Resultado y alcance

Se incorpora un pipeline local de investigación, un motor en memoria y contratos
para futuras fuentes de eventos. Las fórmulas y parámetros V3.1 permanecen:
capital 100000, riesgo individual 1%, total 3%, máximo tres posiciones,
slippage 2 bps, comisión cero, stop ATR×1.5 y objetivo nominal 2R.
No hubo búsqueda ni optimización de parámetros.

La búsqueda de Parquet/CSV/Feather/bases locales en `/workspace`, incluidos
library-files, shared y scratch, no encontró históricos de mercado. No se afirma
validación histórica ni capacidad predictiva. Todos los datos de pruebas son
sintéticos. No se leyeron secretos ni se usaron credenciales de mercado.

## Auditoría por etapa

| Etapa | Hallazgo / decisión | Estado |
| --- | --- | --- |
| Descarga | Feed IEX, SDK paginado; consulta relativa a ahora, sin snapshot identificable hasta congelar bytes. Escritura inicial no atómica y sin maestro de símbolos esperado | Pendiente; no ejecutar automáticamente |
| Actualización | Antes reemplazaba snapshot aunque hubiera símbolos fallidos | Corregido: aborta antes de reemplazar si hubo excepción |
| Almacenamiento | Rutas fijas y scripts con efectos al importar | Motor y transformaciones extraídos; scripts antiguos conservados como adaptadores compatibles |
| Calidad | Vacío y símbolo nulo/vacío podían pasar sin error | Corregido |
| Splits | Salto entre sesiones escapaba a control limitado a minutos contiguos | Advertencia nueva; no identifica causalmente splits ni ajusta precios |
| Indicadores | EMA/RSI/ATR/volumen relativo mantienen estado entre sesiones; VWAP diario | Decisión de estrategia preservada, no usa futuro |
| Señales | Necesitan continuidad, indicadores completos y condiciones originales | Fórmulas conservadas; prueba de prefijo temporal |
| Candidatos | Niveles usan apertura siguiente; no high/low/close siguiente | Conservado como modelo de ejecución; requiere política futura de latencia |
| Backtest | Sin operaciones se trataba como fallo | Corregido: tablas con esquema y curva de capital válidas |
| Backtest | Candidatos no contiguos o sin vela desaparecían silenciosamente | Corregido: error explícito |
| Contabilidad | Se verifica equity, realizado, efectivo y presupuesto de riesgo | Regresiones heredadas pasan; no equivale al margen de un bróker |
| Determinismo | Orden simultáneo por símbolo; dos ejecuciones comparadas exactamente | Implementado; prioridad alfabética es una decisión que debe declararse |

## Arquitectura y compatibilidad

`trading_ia.backtest.simular(velas, candidatas, config, exigir_calidad)` recibe
copias de DataFrames y devuelve operaciones, rechazos y curva. No lee/escribe
archivos, no consulta cuentas y no envía órdenes. `Configuracion` es inmutable.
`backtesting_v3_1.ejecutar()` mantiene constantes, rutas y resumen originales;
construye la configuración y delega en el motor. La suite previa valida esta
compatibilidad. La API del motor cambia deliberadamente solo los errores de
candidatos huérfanos/no contiguos y el resultado vacío.

`trading_ia.transformaciones` contiene las funciones originales de Wilder,
indicadores, señales y candidatos. Los scripts existentes las importan. La CLI
nueva utiliza estas funciones directamente, sin ejecutar scripts con efectos.
La escritura del pipeline se aísla en un directorio nuevo; un error deja un
reporte con estado ERROR, nunca debe interpretarse como investigación exitosa.

## Reproducibilidad y ejecución con datos reales

En el equipo autorizado que contiene el histórico:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest -q
```

Congelar el dataset fuera de Git. Crear `procedencia.json` local con:

```json
{
  "dataset_id": "identificador-y-version-del-snapshot",
  "fuente": "proveedor y feed autorizados",
  "licencia": "referencia local a autorización aplicable",
  "ajuste": "raw o adjusted, política y corporate actions revisadas",
  "tipo": "real"
}
```

Obtener SHA-256 de una copia inmutable, por ejemplo `sha256sum datos.parquet`
(Linux) o `shasum -a 256 datos.parquet` (macOS). Ejecutar con ese valor:

```bash
python -m trading_ia.investigacion datos.parquet \
  --sha256 SHA256_DE_64_CARACTERES \
  --procedencia procedencia.json --salida artefactos/ejecucion-001
```

El directorio de salida debe ser nuevo. Código 0 significa completado; 2 indica
error. `ejecucion.json` registra hash esperado/observado, procedencia, Python,
dependencias instaladas, commit, hashes del código, parámetros, calidad original
y regular, etapa, advertencias y errores. Salidas Parquet: indicadores, señales,
candidatos, operaciones, rechazos y curva, con hashes y número de filas.
La comparación de determinismo se hace en memoria para evitar confundir cambios
de serialización Parquet entre versiones con cambios económicos. Para comparar
máquinas, conservar las mismas versiones y comparar también tablas decodificadas.
No modificar el archivo durante la ejecución: SHA identifica bytes, no garantiza
inmutabilidad si otro proceso los cambia después de verificarlos.

Las advertencias de corporate actions requieren revisión humana antes de usar
métricas. La CLI no certifica que un dataset sea ajustado o tenga licencia válida.
Conservar `procedencia.json`, datos y resultados localmente: pueden contener
información restringida. `work/`, `artefactos/` y Parquet están excluidos de Git.
No utilizar `main.py` como entrada: consulta una cuenta y no valida el pipeline.

## Evidencia de pruebas

Se instaló en un venv limpio Python 3.12 con las versiones fijadas existentes.
`pip check`: sin incompatibilidades. La suite original tuvo 42 pruebas aprobadas
tras extraer el motor; la suite ampliada añade pruebas de pipeline y límites.
Resultados concretos finales en `RESULTADOS_FASE_3.md`. El workflow manual añadido ejecuta
solo pruebas sintéticas, sin credenciales ni conexión a Alpaca. No se han observado
aún sus resultados remotos y no se disparó un workflow manual.

## Interfaces futuras para IA

`Evento` requiere identidad, tipo, fuente, SHA-256 del contenido, revisión,
símbolos y timestamps con zona: ocurrido, publicado y recibido. La disponibilidad
es el máximo entre publicación y recepción. Un evento macro futuro puede tener
fecha de ocurrencia posterior a publicación, sin que eso autorice usar valores
revisados futuros. `FuenteEventos` obliga a consultar hasta un instante de corte.
Cada revisión debe almacenarse como versión inmutable, nunca sobrescribir su
historia. Falta implementar adaptadores, verificación documental de timestamps,
licencias y joins point-in-time. No hay señales ni decisiones basadas en noticias.

## Limitaciones y riesgos pendientes

- No hay evidencia histórica real ni regresión contra un fixture privado autorizado.
- Datos ajustados a posteriori pueden introducir información futura; faltan maestro
  point-in-time de acciones corporativas, delistings y universo sin sesgo de supervivencia.
- El control de saltos es heurístico: splits pequeños, dividendos y correcciones
  pueden no detectarse. No se deben inferir ajustes a partir del precio solamente.
- Un símbolo enteramente ausente no se detecta sin universo esperado externo.
  Respuestas vacías del proveedor aún requieren política explícita de cobertura.
- La calidad estricta bloquea halts y minutos IEX legítimamente ausentes; es una
  limitación de infraestructura deliberada, no una señal de estrategia.
- Sin modelar profundidad, spread variable, fills parciales, borrow, margen real,
  participación, latencia ni financiación. Stop primero en doble toque y prioridad
  alfabética simultánea se conservan. Los gaps pueden superar el riesgo nominal.
- La apertura siguiente para niveles está disponible al ejecutar, no al emitir la
  señal anterior: el modelo presupone construir niveles y fill en esa apertura.
- Modo diagnóstico de sesiones truncadas conoce el último dato observado. Solo
  calidad estricta habilita resultados de investigación; no usar diagnóstico para
  publicar rendimiento.
- La suite prueba prefijos y determinismo, no demuestra ausencia de todo lookahead.
- Los scripts históricos V1/V2/V3 y automatismos siguen sin refactor integral.
- Dependencias fijadas sin hashes; el reporte captura versiones, no garantiza una
  reconstrucción binaria idéntica en otra plataforma.

## Revisión adicional: ejecución de señales y latencia

El modelo V3.1 se conserva como baseline (`modelo_ejecucion=v31`).
Sus niveles se calculan usando el `open` de la vela inmediatamente
posterior a la señal y el simulador presupone fill en dicha apertura,
con slippage fijo. Esta convención puede ser optimista, pues no modela
la latencia necesaria para observar el precio y enviar la orden.

Como alternativa investigable se incluye
`trading_ia.ejecucion.preparar_diferido` y la opción
`--modelo-ejecucion diferido_1m` de la CLI. En este modelo:

1. La señal se conoce al cierre de su propia vela.
2. Los niveles SL/TP se fijan con el cierre de la vela de señal y el ATR
   disponible en ella, sin consultar la apertura posterior.
3. Se espera una vela completa y se intenta entrar en la siguiente
   apertura (dos timestamps de inicio de vela después de la señal).
4. La simulación rechaza niveles invalidados por gaps/slippage. No
   actualiza retrospectivamente stop o take profit usando el precio futuro.
5. Se exigen ambas barras intermedias, continuidad y misma sesión.

Ejemplo local, usando una copia inmutable autorizada del dataset:

```bash
python -m trading_ia.investigacion datos.parquet \\
  --sha256 SHA256_DE_64_CARACTERES \\
  --procedencia procedencia.json \\
  --modelo-ejecucion diferido_1m \\
  --salida artefactos/diferido-001
```

Usar un directorio diferente para V3.1 y comparar los informes de
ambas ejecuciones con **el mismo hash del dataset**. La variante no
garantiza fills, ausencia de selección adversa, microestructura real,
liquidez, spread variable ni rentabilidad. La CLI registra el nombre de
modelo y la latencia configurada para evitar confundir experimentos.
