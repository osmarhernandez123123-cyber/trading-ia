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



def _verificar_consistencia_comparacion(comparacion: dict, plan: dict) -> None:
    """Contrasta etiquetas y resúmenes internos; no recalcula operaciones."""
    if type(comparacion.get("schema_version")) is not int or comparacion["schema_version"] != 1:
        raise ValueError("Versión de comparación OOS inválida")
    if (comparacion.get("id_baseline") != plan["baseline_id"]
            or comparacion.get("id_candidata") != plan["candidata_id"]):
        raise ValueError("Identificadores de comparación no coinciden con el plan")

    filas = comparacion.get("por_ventana")
    if not isinstance(filas, list) or not filas or any(not isinstance(f, dict) for f in filas):
        raise ValueError("Ventanas de comparación ausentes o inválidas")
    if (filas[0].get("inicio_prueba") != plan["inicio_prueba"]
            or filas[-1].get("fin_prueba") != plan["fin_prueba"]):
        raise ValueError("Límites de comparación no coinciden con el plan")

    for nombre in ("baseline", "candidata"):
        agregado = comparacion.get(nombre)
        if not isinstance(agregado, dict) or not isinstance(agregado.get("por_ventana"), list):
            raise ValueError(f"Resumen {nombre} ausente o inválido")
        bloques = agregado["por_ventana"]
        if (type(agregado.get("ventanas")) is not int
                or agregado["ventanas"] != len(filas) or len(bloques) != len(filas)
                or type(agregado.get("operaciones")) is not int
                or agregado["operaciones"] < 0):
            raise ValueError(f"Totales de ventanas {nombre} inconsistentes")
        suma = 0
        for fila, bloque in zip(filas, bloques):
            if not isinstance(bloque, dict) or any(
                fila.get(campo) != bloque.get(campo)
                for campo in ("inicio_prueba", "fin_prueba")
            ):
                raise ValueError(f"Fechas por ventana {nombre} inconsistentes")
            cantidad = bloque.get("operaciones")
            if (type(cantidad) is not int or cantidad < 0
                    or fila.get(f"operaciones_{nombre}") != cantidad
                    or type(fila.get(f"operaciones_{nombre}")) is not int):
                raise ValueError(f"Conteos por ventana {nombre} inconsistentes")
            suma += cantidad
        if suma != agregado["operaciones"]:
            raise ValueError(f"Total de operaciones {nombre} inconsistente")

    # No confiar en una diferencia descriptiva adulterada aunque el SHA del
    # reporte se haya vuelto a calcular: debe derivarse de las medias R
    # declaradas en los resúmenes de la MISMA ventana.
    def expectativa_valida(valor: object, operaciones: int) -> bool:
        return (valor is None if operaciones == 0 else
                type(valor) in (int, float) and math.isfinite(valor))

    for indice, (fila, b, c) in enumerate(zip(
        filas, comparacion["baseline"]["por_ventana"],
        comparacion["candidata"]["por_ventana"],
    ), start=1):
        for nombre, bloque in (("baseline", b), ("candidata", c)):
            cantidad = bloque["operaciones"]
            expectativa = bloque.get("expectativa_r")
            campo = f"expectativa_r_{nombre}"
            declarada = fila.get(campo)
            if ("expectativa_r" not in bloque
                    or not expectativa_valida(expectativa, cantidad)
                    or campo not in fila
                    or not expectativa_valida(declarada, cantidad)
                    or declarada != expectativa):
                raise ValueError(f"Expectativa R {nombre} inconsistente en ventana {indice}")
        delta = (c["expectativa_r"] - b["expectativa_r"]
                 if b["operaciones"] and c["operaciones"] else None)
        if delta is not None and not math.isfinite(delta):
            raise ValueError(f"Diferencia media R no finita en ventana {indice}")
        campo = "diferencia_media_r_descriptiva"
        declarado = fila.get(campo)
        if (campo not in fila
                or not expectativa_valida(declarado, int(delta is not None))
                or declarado != delta):
            raise ValueError(f"Diferencia media R inconsistente en ventana {indice}")

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
    _verificar_consistencia_comparacion(reporte["comparacion"], registro["plan"])
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
