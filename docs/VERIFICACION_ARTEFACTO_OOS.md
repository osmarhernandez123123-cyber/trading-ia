# Verificación local de artefactos OOS serializados

`trading_ia.verificacion_artefacto_oos` comprueba **tres compromisos
externos** sin subir archivos: SHA-256 de los **bytes exactos** del JSON
del reporte OOS, SHA-256 canónico del plan incluido y SHA-256 del dataset
**declarado** dentro de ese plan. También rechaza claves JSON duplicadas,
valores no finitos, esquema incompatible y archivos mayores de 16 MiB.

## Ejecución local (sin órdenes ni broker)

Una vez generado y guardado el reporte JSON en el Mac, conservar por separado
sus bytes y tres hashes de referencia previamente registrados. La huella del
reporte debe capturarse cuando se congela ese artefacto, no reconstruirse
desde el archivo que se pretende verificar. Ejecutar:

```bash
python -m trading_ia.verificacion_artefacto_oos \
  --reporte reportes/oos-registrado.json \
  --sha256-reporte-esperado <sha256-externo-del-reporte> \
  --sha256-plan-esperado <sha256-externo-del-plan> \
  --sha256-dataset-esperado <sha256-externo-del-dataset>
```

La salida contiene **solo** hashes, tamaño y advertencia; no incluye
operaciones, rutas locales, precios, credenciales ni el contenido del
reporte. No modifica el archivo. Para uso programático:

```python
from trading_ia.verificacion_artefacto_oos import verificar_artefacto_oos

resumen = verificar_artefacto_oos(
    bytes_reporte_local,
    reporte_sha256_esperado=huella_reporte_guardada,
    plan_sha256_esperado=huella_plan_guardada,
    dataset_sha256_esperado=huella_dataset_guardada,
)
```

## Coherencia estructural de la comparación

Además de los hashes, el verificador exige que las identidades de baseline y
candidata coincidan con el plan y que las fechas, conteos y totales declarados
por ventana concuerden entre la comparación y sus dos resúmenes. También
exige que las medias R declaradas en cada resumen coincidan con la comparación
y que la diferencia descriptiva sea exactamente `media_candidata - media_baseline`
cuando ambas ventanas tienen operaciones; si alguna está vacía, sus medias
o la diferencia correspondiente deben ser `null` según corresponda. Rechaza
informes con resúmenes ausentes o contradictorios aunque se haya recalculado
el hash del archivo. **No reconstruye sesiones XNYS ni recalcula operaciones,
PnL, medias R desde operaciones o rentabilidad**: una estructura coherente puede contener cifras falsas.
El fixture de pruebas representa solo coherencia estructural sintética.

## Límites de seguridad y alcance

La verificación confirma que **el reporte no cambió respecto a la huella
externa proporcionada** y que el plan interno coincide con su propia huella
canónica y con las referencias suministradas. **No abre ni calcula el hash
del dataset real**, no verifica fills, OHLCV, calidad, licencias, identidad
del proveedor, fecha de preregistro, estrategia ejecutada ni rentabilidad.
Si un atacante puede reemplazar simultáneamente archivos y hashes externos,
el control no detecta la sustitución. Mantener compromisos independientes,
fechados y fuera del directorio de resultados; nunca subir históricos
privados ni secretos al repositorio. El límite de 16 MiB aplica a bytes
serializados del reporte, no a datasets.

Pruebas enteramente sintéticas:

```bash
python -m pytest -q tests/test_verificacion_artefacto_oos.py
```
