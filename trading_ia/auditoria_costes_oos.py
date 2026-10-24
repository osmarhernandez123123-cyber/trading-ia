"""Auditoría aritmética de costes simulados vinculada a un plan OOS.

No obtiene precios, no valida fills y no envía órdenes. Solo comprueba
coherencia de campos declarados con el coste congelado del plan.
"""
from __future__ import annotations

import hmac
import math
import re
from collections.abc import Mapping

import numpy as np
import pandas as pd

from .registro_plan_oos import registrar_plan_oos


COLUMNAS = frozenset({
    "nocional_entrada_usd", "nocional_salida_usd", "pnl_bruto_usd",
    "coste_total_usd", "pnl_usd", "riesgo_total", "R",
})
ADVERTENCIA = (
    "Auditoría aritmética de costes declarados: no comprueba que los "
    "nocionales, precios, fills, PnL bruto o hashes de datos sean auténticos. "
    "La huella suministrada no acredita fecha de pre-registro. "
    "No demuestra rentabilidad ni sustituye el backtest."
)


def _numeros(df: pd.DataFrame, columna: str) -> np.ndarray:
    valores = df[columna]
    if not valores.map(
        lambda v: isinstance(v, (int, float, np.integer, np.floating))
        and not isinstance(v, (bool, np.bool_))
    ).all():
        raise ValueError(f"{columna}: se requieren números, no texto o booleanos")
    try:
        resultado = pd.to_numeric(valores, errors="raise").to_numpy(dtype=float)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{columna}: valores no representables") from exc
    if not np.isfinite(resultado).all():
        raise ValueError(f"{columna}: valores no finitos")
    return resultado


def auditar_costes_plan_oos(
    plan: Mapping[str, object],
    *,
    plan_sha256_esperado: str,
    operaciones: pd.DataFrame,
) -> dict:
    """Comprueba coste por ambos lados, PnL neto y R sin mutar operaciones.

    Se exige compromiso SHA-256 externo del plan, pero no se verifica cuándo
    se creó. El nocional de entrada y el de salida se declaran por separado;
    no se infiere ningún precio ni ejecución de mercado.
    """
    if not isinstance(plan_sha256_esperado, str) or not re.fullmatch(
        r"[0-9a-f]{64}", plan_sha256_esperado
    ):
        raise ValueError("plan_sha256_esperado inválido")
    registro = registrar_plan_oos(plan)
    if not hmac.compare_digest(registro["plan_sha256"], plan_sha256_esperado):
        raise ValueError("La huella del plan no coincide")
    if not isinstance(operaciones, pd.DataFrame):
        raise ValueError("operaciones debe ser DataFrame")
    if not operaciones.columns.is_unique or not COLUMNAS.issubset(operaciones.columns):
        raise ValueError("Columnas de auditoría de costes faltantes o duplicadas")

    valores = {campo: _numeros(operaciones, campo) for campo in COLUMNAS}
    entrada = valores["nocional_entrada_usd"]
    salida = valores["nocional_salida_usd"]
    riesgo = valores["riesgo_total"]
    coste = valores["coste_total_usd"]
    if (entrada <= 0).any() or (salida <= 0).any() or (riesgo <= 0).any():
        raise ValueError("Nocionales y riesgo deben ser positivos")
    if (coste < 0).any():
        raise ValueError("El coste declarado debe ser no negativo")

    factor = registro["plan"]["coste_bps_por_lado"] / 10_000
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        esperado = entrada * factor + salida * factor
        neto = valores["pnl_bruto_usd"] - coste
        r_calculada = neto / riesgo
    if not (np.isfinite(esperado).all() and np.isfinite(neto).all()
            and np.isfinite(r_calculada).all()):
        raise ValueError("Aritmética de costes no finita")
    if not np.allclose(coste, esperado, rtol=1e-10, atol=1e-6):
        raise ValueError("Coste declarado incompatible con bps del plan")
    if not np.allclose(valores["pnl_usd"], neto, rtol=1e-10, atol=1e-6):
        raise ValueError("PnL neto incompatible con bruto menos costes")
    if not np.allclose(valores["R"], r_calculada, rtol=1e-6, atol=1e-8):
        raise ValueError("R incompatible con PnL neto y riesgo")

    total = float(np.sum(coste, dtype=np.float64))
    if not math.isfinite(total):
        raise ValueError("Coste agregado no finito")
    return {
        "schema_version": 1,
        "plan_sha256": registro["plan_sha256"],
        "coste_bps_por_lado": registro["plan"]["coste_bps_por_lado"],
        "operaciones_auditadas": len(operaciones),
        "coste_total_declarado_usd": total,
        "advertencia": ADVERTENCIA,
    }
