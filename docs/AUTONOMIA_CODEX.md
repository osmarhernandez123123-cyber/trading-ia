# Automatización de Codex por API — retirada

El 11 de noviembre de 2026 se retiró el flujo de GitHub Actions
`codex-autonomo.yml`, que estaba deshabilitado y tenía referencias
a una credencial de una API con facturación independiente.

El proyecto no debe activar servicios de pago ni guardar claves,
contraseñas, tokens o archivos de cuentas en GitHub.
Las pruebas de software restantes no necesitan credenciales externas.

## Precaución con credenciales históricas

Eliminar un archivo de GitHub **no revoca** credenciales, ni elimina sus
copias antiguas en commits, ramas, PR, logs o archivos descargados.

Si se guardó un secreto en GitHub Actions, el propietario debe revisar
**Settings → Secrets and variables → Actions**, eliminar las entradas que
ya no necesita y revocar/rotar las credenciales en el proveedor que las
emitió. El acceso a esos secretos no está disponible en esta integración.

Para los scripts que legítimamente necesitan acceso a datos de Alpaca,
utilizar únicamente variables de entorno locales, nunca valores literales.
El repositorio debe permanecer sin acceso a operaciones LIVE.
