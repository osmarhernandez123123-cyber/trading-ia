# Codex por API — desactivado a petición del usuario

**Estado actual (17 de octubre de 2026): DESACTIVADO.** No hay cron de Codex API y el job está bloqueado incluso ante ejecución manual. El usuario eligió seguir sin costes adicionales mediante la automatización existente de ChatGPT y las pruebas gratuitas disponibles de GitHub Actions. No se necesita ni se debe configurar `OPENAI_API_KEY`. Los pasos siguientes quedan solo como documentación histórica para una futura decisión expresa.

## Procedimiento opcional (no activo)

Esta integración utiliza **OpenAI API** con facturación independiente de la
suscripción ChatGPT/Codex Cloud. La variante de GitHub Action ejecuta el
Codex CLI en un runner GitHub, no crea automáticamente tareas en Codex Cloud.

## Estado de seguridad
- Ninguna credencial está incluida en el repositorio.
- El workflow programado se omite si no existe el secreto
  `OPENAI_API_KEY`. No consume API cuando está omitido.
- Ejecuta como máximo una iteración programada al día (06:17 UTC),
  y omite nuevas iteraciones si existe un PR automático sin integrar.
- La duración máxima del job de desarrollo es 50 minutos. **No es un límite
  monetario**: revisar el consumo facturado en la API.
- El job con acceso de desarrollo de Codex solo tiene lectura de GitHub.
  El job de publicación recibe un parche, y solo publica cambios en
  `trading_ia/`, `tests/` y `docs/`, sin ejecutar el parche con
  permisos de escritura al repositorio.
- Todos los cambios quedan en un Pull Request separado. No hay auto-merge.
- No se permite operar con dinero real ni publicar secretos o datos privados.

## Activación (requiere acción del propietario)
1. Revisar la facturación de OpenAI API y establecer límites/alertas de
   gasto adecuados. No aceptar cargos sin revisar condiciones.
2. Crear una API key específica del proyecto en
   https://platform.openai.com/api-keys (no compartirla en chats).
3. En GitHub, abrir el repositorio > Settings > Secrets and variables >
   Actions > New repository secret. Nombrar el secreto `OPENAI_API_KEY`.
4. Para creación automática de PRs con el token de Actions, habilitar
   Settings > Actions > General > Workflow permissions >
   `Allow GitHub Actions to create and approve pull requests`.
   La opción no autoriza fusionarlos por sí sola.
5. Integrar este PR y confirmar que el workflow está en main. Cuando
   exista el secreto, las ejecuciones programadas podrán operar.

## Seguimiento
- Revisar Actions > `Codex - desarrollo autónomo (opt-in)`.
- Cada ejecución crea una rama `codex/auto-<run_id>` y un PR si
  encuentra un cambio que pase los tests.
- Si existe un PR autónomo abierto, el siguiente ciclo se omite para
  evitar PRs duplicados y consumos innecesarios.
- Si el runner falla por límites de API, repositorio, permisos o
  conflictos de base, no tratar la tarea como terminada.
- Las tareas ChatGPT de seguimiento pueden revisar GitHub, comentar
  defectos y apoyar la integración. No es el mismo planificador que Codex.
