# Vínculo local de parámetros con plan OOS

`trading_ia.vinculo_parametros_oos.verificar_parametros_oos` comprueba
que los **bytes exactos** de las dos configuraciones de estrategia coincidan
con `baseline_parametros_sha256` y `candidata_parametros_sha256` del plan
OOS. Antes de comprobar los archivos exige que la huella canónica del plan
coincida con un SHA-256 **guardado independientemente**.

## Uso local (sin datos de mercado)

```python
from pathlib import Path
from trading_ia.vinculo_parametros_oos import verificar_parametros_oos

resultado = verificar_parametros_oos(
    plan_congelado,
    plan_sha256_esperado=compromiso_externo_guardado,
    baseline_bytes=Path("config/base.json").read_bytes(),
    candidata_bytes=Path("config/candidata.json").read_bytes(),
)
```

Las configuraciones deben ser archivos pequeños (entre 1 byte y 1 MiB).
Se calcula SHA-256 sobre los **bytes**, sin interpretar, reordenar ni
normalizar JSON: un cambio de espacios también cambia la huella.
La función no abre archivos, no modifica el plan y solo devuelve hashes,
tamaños y una advertencia; no devuelve contenido, rutas ni secretos.
No subir configuraciones privadas ni credenciales al repositorio.

Este control cubre una laguna del registro de plan: antes solo se
validaba la *forma* de los hashes declarados; ahora se pueden contrastar
con configuraciones locales reales. **No demuestra** que el motor haya
usado esas configuraciones, que el código o dependencias fueran los
esperados, ni que el compromiso se guardara antes de ver OOS. No verifica
datos, operaciones, fills ni rentabilidad. Para reproducibilidad completa
todavía hace falta vincular código, entorno y ejecución verificable.

Pruebas sintéticas: `python -m pytest -q tests/test_vinculo_parametros_oos.py`.
