"""Contrasta los bytes de parámetros locales con un plan OOS congelado.

No abre archivos ni ejecuta estrategias; las huellas esperadas deben venir
de un compromiso independiente, anterior a la evaluación fuera de muestra.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping

from .registro_plan_oos import registrar_plan_oos


MAX_PARAMETROS_BYTES = 1024 * 1024


def verificar_parametros_oos(
    plan: Mapping[str, object],
    *,
    plan_sha256_esperado: str,
    baseline_bytes: bytes,
    candidata_bytes: bytes,
) -> dict:
    """Verifica los bytes exactos de ambas configuraciones frente al plan.

    No interpreta ni normaliza JSON/YAML: cambiar un byte exige una huella
    nueva. No acredita que esos parámetros fueran usados por el backtest.
    """
    if (not isinstance(plan_sha256_esperado, str)
            or re.fullmatch(r"[0-9a-f]{64}", plan_sha256_esperado) is None):
        raise ValueError("plan_sha256_esperado debe ser SHA-256 en minúsculas")
    registro = registrar_plan_oos(plan)
    if not hmac.compare_digest(registro["plan_sha256"], plan_sha256_esperado):
        raise ValueError("El plan no coincide con su compromiso externo")

    resultado = {
        "schema_version": 1,
        "plan_sha256": registro["plan_sha256"],
    }
    for nombre, contenido in (
        ("baseline", baseline_bytes),
        ("candidata", candidata_bytes),
    ):
        if (type(contenido) is not bytes
                or not 0 < len(contenido) <= MAX_PARAMETROS_BYTES):
            raise ValueError(f"Parámetros {nombre}: se exigen bytes no vacíos de hasta 1 MiB")
        huella = hashlib.sha256(contenido).hexdigest()
        esperada = registro["plan"][f"{nombre}_parametros_sha256"]
        if not hmac.compare_digest(huella, esperada):
            raise ValueError(f"Parámetros {nombre}: SHA-256 distinto del plan")
        resultado[f"{nombre}_parametros_sha256"] = huella
        resultado[f"{nombre}_parametros_bytes"] = len(contenido)

    resultado["advertencia"] = (
        "Coincidencia de bytes y plan declarado; no verifica ejecución efectiva, "
        "código, entorno, fecha de preregistro, fills ni rentabilidad."
    )
    return resultado
