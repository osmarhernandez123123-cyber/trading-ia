"""Pruebas sintéticas: sin datos privados, red ni broker."""
import copy
import hashlib
import json

import pytest

from trading_ia.registro_plan_oos import registrar_plan_oos


def ejemplo():
    return {
        "schema_version": 1,
        "dataset_sha256": "a" * 64,
        "baseline_id": "V3.1",
        "candidata_id": "modelo-B",
        "baseline_parametros_sha256": "b" * 64,
        "candidata_parametros_sha256": "c" * 64,
        "universo": ["MSFT", "AAPL"],
        "inicio_prueba": "2026-01-01",
        "fin_prueba": "2026-03-01",
        "coste_bps_por_lado": 2,
        "ventanas": {
            "entrenamiento": 10, "validacion": 5, "prueba": 3,
            "embargo": 2, "horizonte_etiqueta": 2, "paso": 3,
        },
        "hipotesis": "  La candidata no mejora después de costes.  ",
    }


def test_huella_determinista_y_entrada_inmutable():
    plan = ejemplo()
    antes = copy.deepcopy(plan)
    a = registrar_plan_oos(plan)
    b_plan = copy.deepcopy(plan)
    b_plan["universo"] = ("AAPL", "MSFT")
    b_plan["coste_bps_por_lado"] = 2.0
    b_plan["ventanas"] = dict(reversed(list(b_plan["ventanas"].items())))
    b = registrar_plan_oos(b_plan)
    assert a["plan_sha256"] == b["plan_sha256"]
    assert a["plan"]["universo"] == ["AAPL", "MSFT"]
    assert a["plan"]["hipotesis"] == "La candidata no mejora después de costes."
    assert plan == antes
    assert len(a["plan_sha256"]) == 64
    canonical = json.dumps(
        a["plan"], sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    assert a["plan_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert "no demuestra" in a["advertencia"]


@pytest.mark.parametrize("campo,nuevo", [
    ("dataset_sha256", "d" * 64),
    ("candidata_parametros_sha256", "e" * 64),
    ("universo", ["AAPL", "NVDA"]),
    ("fin_prueba", "2026-03-02"),
    ("coste_bps_por_lado", 3),
    ("hipotesis", "Otra hipótesis."),
    ("ventanas", {
        "entrenamiento": 11, "validacion": 5, "prueba": 3,
        "embargo": 2, "horizonte_etiqueta": 2, "paso": 3,
    }),
])
def test_huella_cambia_con_configuracion(campo, nuevo):
    plan = ejemplo()
    original = registrar_plan_oos(plan)["plan_sha256"]
    plan[campo] = nuevo
    assert registrar_plan_oos(plan)["plan_sha256"] != original


@pytest.mark.parametrize("modificacion", [
    {"resultado_oos": {"pnl": 1000}},
    {"schema_version": 2},
    {"schema_version": True},
])
def test_rechaza_campos_de_resultados_o_version(modificacion):
    plan = ejemplo()
    plan.update(modificacion)
    with pytest.raises(ValueError):
        registrar_plan_oos(plan)


def test_rechaza_campo_faltante():
    plan = ejemplo()
    del plan["hipotesis"]
    with pytest.raises(ValueError, match="Campos"):
        registrar_plan_oos(plan)


@pytest.mark.parametrize("valor", ["A" * 64, "0" * 63, "g" * 64, None, 123])
def test_rechaza_sha256_ambiguo(valor):
    plan = ejemplo()
    plan["dataset_sha256"] = valor
    with pytest.raises(ValueError, match="SHA-256"):
        registrar_plan_oos(plan)


@pytest.mark.parametrize("ids", [
    ("V3.1", "v3.1"), ("", "B"), (" con espacios ", "B"),
    ("A", None), ("A/B", "B"),
])
def test_rechaza_ids_ambiguos(ids):
    plan = ejemplo()
    plan["baseline_id"], plan["candidata_id"] = ids
    with pytest.raises(ValueError, match="identificador|distintos"):
        registrar_plan_oos(plan)


@pytest.mark.parametrize("universo", [
    [], ["AAPL", "AAPL"], ["aapl"], ["AAPL", " MSFT"],
    ["AAPL", None], "AAPL", ["BRK/B"],
])
def test_rechaza_universo_invalido(universo):
    plan = ejemplo()
    plan["universo"] = universo
    with pytest.raises(ValueError, match="universo"):
        registrar_plan_oos(plan)


@pytest.mark.parametrize("fecha", [
    "2026-02-30", "2026-1-2", "20260102",
    "2026-01-02T00:00:00", None,
])
def test_rechaza_fechas_no_iso(fecha):
    plan = ejemplo()
    plan["inicio_prueba"] = fecha
    with pytest.raises(ValueError, match="ISO"):
        registrar_plan_oos(plan)


def test_rechaza_rango_invertido():
    plan = ejemplo()
    plan["inicio_prueba"] = "2026-04-01"
    with pytest.raises(ValueError, match="invertido"):
        registrar_plan_oos(plan)


@pytest.mark.parametrize("coste", [
    -1, float("nan"), float("inf"), float("-inf"), True, "2",
])
def test_rechaza_costes_invalidos(coste):
    plan = ejemplo()
    plan["coste_bps_por_lado"] = coste
    with pytest.raises(ValueError, match="coste_bps"):
        registrar_plan_oos(plan)


@pytest.mark.parametrize("clave,valor,patron", [
    ("prueba", 0, "enteros positivos"),
    ("paso", 2, "solapado"),
    ("embargo", 1, "horizonte"),
    ("validacion", True, "enteros positivos"),
])
def test_rechaza_ventanas_inseguras(clave, valor, patron):
    plan = ejemplo()
    plan["ventanas"][clave] = valor
    with pytest.raises(ValueError, match=patron):
        registrar_plan_oos(plan)


def test_rechaza_ventanas_con_campos_extra():
    plan = ejemplo()
    plan["ventanas"]["resultados"] = 5
    with pytest.raises(ValueError, match="ventanas"):
        registrar_plan_oos(plan)


@pytest.mark.parametrize("hipotesis", ["", "   ", "x" * 501, None])
def test_rechaza_hipotesis_vacia_o_excesiva(hipotesis):
    plan = ejemplo()
    plan["hipotesis"] = hipotesis
    with pytest.raises(ValueError, match="hipotesis"):
        registrar_plan_oos(plan)
