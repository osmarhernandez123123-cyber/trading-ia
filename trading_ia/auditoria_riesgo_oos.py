"""Auditoría descriptiva de presupuestos de riesgo en trades OOS cerrados.

Solo examina registros ya producidos; no consulta precios ni envía órdenes.
Los límites son porcentajes del capital INICIAL fijo, no del patrimonio
variable utilizado por el motor de backtest.
"""
from __future__ import annotations

import math

import pandas as pd

from .metricas_oos import evaluar_prueba
from .validacion_temporal import VentanaTemporal


ADVERTENCIA_RIESGO = (
    "Auditoría de riesgo declarado ex-ante sobre operaciones cerradas. "
    "Usa capital inicial fijo y posiciones semiabiertas [entrada, salida); "
    "no reconstruye patrimonio intradía, stops ejecutados, fills, "
    "deslizamiento, riesgo de gap ni posiciones ausentes del registro. "
    "No sustituye los controles del simulador ni demuestra rentabilidad."
)


def auditar_riesgo_oos(
    operaciones: pd.DataFrame,
    ventana: VentanaTemporal,
    *,
    capital_inicial: float = 100_000.0,
    limite_operacion_pct: float = 1.0,
    limite_simultaneo_pct: float = 3.0,
) -> dict:
    """Rechaza riesgo individual o simultáneo superior al presupuesto fijo.

    Las salidas liberan presupuesto antes de entradas en el mismo instante.
    Una operación de duración cero no ocupa tiempo, pero sí debe respetar
    el límite individual. La función no modifica el DataFrame de entrada.
    """
    for nombre, valor in (
        ("limite_operacion_pct", limite_operacion_pct),
        ("limite_simultaneo_pct", limite_simultaneo_pct),
    ):
        if (type(valor) not in (int, float)
                or not math.isfinite(valor) or not 0 < valor <= 100):
            raise ValueError(f"{nombre} debe ser porcentaje finito en (0, 100]")
    if limite_operacion_pct > limite_simultaneo_pct:
        raise ValueError("El límite simultáneo no puede ser menor al individual")

    # Reutilizar la validación de esquema, R, timestamps, duplicados y OOS.
    resumen = evaluar_prueba(
        operaciones, ventana, capital_inicial=capital_inicial
    )
    capital = float(capital_inicial)
    maximo_individual = capital * (float(limite_operacion_pct) / 100)
    maximo_simultaneo = capital * (float(limite_simultaneo_pct) / 100)

    eventos = []
    for indice, (entrada, salida, valor) in enumerate(zip(
        operaciones["entrada_timestamp"],
        operaciones["salida_timestamp"],
        operaciones["riesgo_total"],
    )):
        riesgo = float(valor)
        if riesgo > maximo_individual:
            raise ValueError("Riesgo por operación supera límite declarado")
        inicio = pd.Timestamp(entrada).tz_convert("UTC")
        fin = pd.Timestamp(salida).tz_convert("UTC")
        if inicio == fin:
            continue  # Intervalo semiabierto vacío: no hay riesgo abierto.
        eventos.append((inicio, 1, indice, riesgo))
        eventos.append((fin, 0, indice, riesgo))

    activos: dict[int, float] = {}
    pico = 0.0
    for _, tipo, indice, riesgo in sorted(eventos):
        if tipo == 0:
            del activos[indice]
        else:
            activos[indice] = riesgo
            try:
                actual = math.fsum(activos.values())
            except OverflowError as exc:
                raise ValueError("Riesgo simultáneo agregado no finito") from exc
            if not math.isfinite(actual):
                raise ValueError("Riesgo simultáneo agregado no finito")
            if actual > maximo_simultaneo:
                raise ValueError("Riesgo simultáneo supera límite declarado")
            pico = max(pico, actual)

    return {
        "schema_version": 1,
        "operaciones": resumen["operaciones"],
        "capital_inicial_usd": capital,
        "limite_operacion_pct": float(limite_operacion_pct),
        "limite_simultaneo_pct": float(limite_simultaneo_pct),
        "pico_riesgo_simultaneo_usd": pico,
        "pico_riesgo_simultaneo_pct": (pico / capital) * 100,
        "advertencia": ADVERTENCIA_RIESGO,
    }
