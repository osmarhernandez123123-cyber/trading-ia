# Alpaca Paper Trading — integración exclusivamente simulada

## Autorización y límites
El propietario autorizó usar **únicamente la cuenta paper de Alpaca** para
pruebas experimentales. Esta autorización **no incluye** dinero real, endpoints
LIVE ni credenciales de producción. No implica que una estrategia sea rentable.

La implementación inicial (`trading_ia.alpaca_paper`) es de **solo lectura**:
consulta un resumen de cuenta sin leer ni almacenar identificadores de cuenta.
No puede enviar ni cancelar órdenes.

## Protección de credenciales
Alpaca separa claves paper/live y endpoints. Este módulo requiere solo:
- `ALPACA_PAPER_API_KEY`
- `ALPACA_PAPER_SECRET_KEY`

La factoría de cliente fija `paper=True` y
`https://paper-api.alpaca.markets`. No reutilizar variables genéricas de claves
en este nuevo componente. No introducir claves en archivos versionados, pruebas,
texto de PRs ni conversaciones.

La cuenta aún **no está enlazada al entorno GitHub** por el hecho de que el
usuario haya autorizado su uso. Los históricos originales y las claves pueden
existir solo en el Mac del usuario. No se debe informar que la conexión real fue
comprobada hasta realizar una consulta remota autorizada.

## Hitos antes de permitir órdenes paper automáticas
1. Verificar conectividad real con credenciales paper y confirmar endpoint.
2. Implementar adaptador de órdenes paper separado del cliente de lectura.
3. Incluir idempotencia, conciliación de órdenes y posiciones, estado durable
   y bloqueo de reenvíos tras caída/reinicio.
4. Añadir limites de riesgo: símbolos permitidos, nocional por operación,
   exposición total, operaciones por sesión y presupuesto de pérdida.
5. Implementar kill switch y respuesta a errores/429/red incompleta.
6. Probar con mocks, paper y registro auditable, sin secretos ni datos privados.
7. Confirmar explícitamente que el modo live no es configurable en este
   adaptador. Por defecto, ninguna estrategia debe enviar órdenes.

La línea base V3.1 ha mostrado esperanza negativa en pruebas históricas previas.
El paper trading es una vía de observación y validación, no una justificación para
pasar a dinero real. Los fills paper pueden diferir de los reales.

## Pruebas
`python -m pytest -q tests/test_alpaca_paper.py` usa un cliente ficticio.
No necesita conexión, datos reales ni credenciales de Alpaca.

Fuentes del proveedor:
- https://alpaca.markets/sdks/python/api_reference/trading/trading-client.html
- https://docs.alpaca.markets/us/docs/working-with-orders
