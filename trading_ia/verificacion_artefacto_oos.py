"""Verifica la integridad de bytes de un reporte OOS serializado localmente.

No lee datasets, no prueba procedencia ni fecha de preregistro y no publica
el contenido del reporte. El compromiso esperado debe obtenerse por fuera.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import re
from pathlib import Path

from .registro_plan_oos import registrar_plan_oos


MAX_REPORTE_BYTES = 16 * 1024 * 1024


def _sha(valor: str, campo: str) -> str:
    if not isinstance(valor, str) or re.fullmatch(r"[0-9a-f]{64}", valor) is None:
        raise ValueError(f"{campo} debe ser SHA-256 hexadecimal en minúsculas")
    return valor


def _objeto_sin_duplicados(pares: list[tuple[str, object]]) -> dict:
    resultado = {}
    for clave, valor in pares:
        if clave in resultado:
            raise ValueError("JSON con clave duplicada")
        resultado[clave] = valor
    return resultado


def _constante_invalida(valor: str) -> None:
    raise ValueError(f"JSON con constante no finita: {valor}")


def _exigir_finitos(raiz: object) -> None:
    pendientes = [raiz]
    while pendientes:
        valor = pendientes.pop()
        if isinstance(valor, float) and not math.isfinite(valor):
            raise ValueError("JSON con número no finito")
        if isinstance(valor, dict):
            pendientes.extend(valor.values())
        elif isinstance(valor, list):
            pendientes.extend(valor)


def verificar_artefacto_oos(
    contenido: bytes,
    *,
    reporte_sha256_esperado: str,
    plan_sha256_esperado: str,
    dataset_sha256_esperado: str,
) -> dict:
    """Verifica bytes y cadena declarada reporte -> plan -> dataset.

    Los tres hashes esperados deben proceder de referencias independientes;
    pasar hashes recién calculados del propio contenido no aporta garantía.
    """
    esperado_reporte = _sha(reporte_sha256_esperado, "reporte_sha256_esperado")
    esperado_plan = _sha(plan_sha256_esperado, "plan_sha256_esperado")
    esperado_dataset = _sha(dataset_sha256_esperado, "dataset_sha256_esperado")
    if type(contenido) is not bytes or not 0 < len(contenido) <= MAX_REPORTE_BYTES:
        raise ValueError("Reporte debe ser bytes no vacíos de hasta 16 MiB")
    actual = hashlib.sha256(contenido).hexdigest()
    if not hmac.compare_digest(actual, esperado_reporte):
        raise ValueError("Huella SHA-256 de reporte no coincide")
    try:
        reporte = json.loads(
            contenido.decode("utf-8"),
            object_pairs_hook=_objeto_sin_duplicados,
            parse_constant=_constante_invalida,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Reporte no es JSON UTF-8 válido") from exc
    _exigir_finitos(reporte)
    if (not isinstance(reporte, dict)
            or type(reporte.get("schema_version")) is not int
            or reporte["schema_version"] != 1
            or not isinstance(reporte.get("comparacion"), dict)):
        raise ValueError("Esquema de reporte OOS inválido")
    plan = reporte.get("plan")
    if not isinstance(plan, dict):
        raise ValueError("Falta plan registrado en reporte")
    registro = registrar_plan_oos(plan)
    huella_plan = _sha(reporte.get("plan_sha256"), "plan_sha256 del reporte")
    if (not hmac.compare_digest(huella_plan, registro["plan_sha256"])
            or not hmac.compare_digest(huella_plan, esperado_plan)):
        raise ValueError("Huella de plan no coincide con plan o compromiso")
    huella_dataset = registro["plan"]["dataset_sha256"]
    if not hmac.compare_digest(huella_dataset, esperado_dataset):
        raise ValueError("Huella declarada de dataset no coincide con referencia")
    return {
        "schema_version": 1,
        "reporte_sha256": actual,
        "plan_sha256": huella_plan,
        "dataset_sha256_declarado": huella_dataset,
        "reporte_bytes": len(contenido),
        "advertencia": (
            "Integridad de bytes y coherencia de huellas declaradas; "
            "no verifica dataset real, fills, fecha de preregistro ni rentabilidad."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reporte", required=True, type=Path)
    parser.add_argument("--sha256-reporte-esperado", required=True)
    parser.add_argument("--sha256-plan-esperado", required=True)
    parser.add_argument("--sha256-dataset-esperado", required=True)
    args = parser.parse_args(argv)
    with args.reporte.open("rb") as archivo:
        contenido = archivo.read(MAX_REPORTE_BYTES + 1)
    resultado = verificar_artefacto_oos(
        contenido,
        reporte_sha256_esperado=args.sha256_reporte_esperado,
        plan_sha256_esperado=args.sha256_plan_esperado,
        dataset_sha256_esperado=args.sha256_dataset_esperado,
    )
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
