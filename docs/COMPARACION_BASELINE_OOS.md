# Comparación descriptiva OOS frente a baseline predefinido

`trading_ia.comparacion_baseline_oos.comparar_baseline_oos` compara **dos**
estrategias fijadas de antemano, con las mismas ventanas de prueba disjuntas
de `crear_ventanas`. Acepta listas de DataFrames con operaciones cerradas,
incluidos fixtures sintéticos. No consulta mercado, broker ni credenciales.

## Contrato de uso

1. Antes de acceder a las pruebas OOS, registrar fuera del código las versiones,
   parámetros, universo histórico, costes y reglas de ambos modelos. Los
   identificadores `id_baseline` e `id_candidata` son etiquetas, **no**
   prueba criptográfica de ese compromiso.
2. Cada secuencia debe tener exactamente un bloque por ventana, en el mismo
   orden. Se reutiliza `agregar_pruebas` para validar integridad de fechas,
   duplicados, PnL/R y ventanas no solapadas **por modelo**.
3. Leer la expectativa R ponderada, el tamaño de muestra y los resúmenes
   individuales. La diferencia de media R **por ventana** se muestra solo
   cuando ambos modelos tienen operaciones; sin operaciones se devuelve null,
   nunca una expectativa ficticia de cero. Si la resta de dos medias finitas
   desborda a infinito, el reporte falla explícitamente en vez de publicar inf.
4. No se devuelve ranking, p-valor, intervalo para diferencias ni recomendación
   de compra. Una comparación no autoriza seleccionar una estrategia usando
   el conjunto de prueba. Si se utiliza el OOS para escoger o ajustar modelos,
   debe reservarse un nuevo bloque de prueba final completamente intacto.

## Limitaciones

La diferencia entre medias R no es un contraste estadístico pareado porque
cada modelo puede operar momentos, símbolos, riesgos y tamaños distintos.
Los resultados pueden estar correlacionados temporalmente. No se comparan
retornos compuestos ni drawdowns de una cartera continua, ni se demuestra
rentabilidad. Comparar la misma definición de riesgo, costes y universo; si
difieren, las medias R pueden no ser directamente interpretables.

El baseline V3.1 no se modifica. Se requieren datos históricos autorizados
para cualquier conclusión sobre desempeño fuera de muestras sintéticas.
