"""Contabilidad de costes OOS con operaciones exclusivamente sintéticas."""
import copy

import pandas as pd
import pytest

from trading_ia.registro_plan_oos import registrar_plan_oos
from trading_ia.auditoria_costes_oos import auditar_costes_plan_oos


def plan_ejemplo():
    return {
        "schema_version": 1,
        "dataset_sha256": "a" * 64,
        "baseline_id": "V3.1",
        "candidata_id": "modelo-B",
        "baseline_parametros_sha256": "b" * 64,
        "candidata_parametros_sha256": "c" * 64,
        "universo": ["AAPL"],
        "inicio_prueba": "2026-01-15",
        "fin_prueba": "2026-01-16",
        "coste_bps_por_lado": 2,
        "ventanas": {
            "entrenamiento": 5, "validacion": 2, "prueba": 2,
            "embargo": 1, "horizonte_etiqueta": 1, "paso": 2,
        },
        "hipotesis": "Sin promesa de edge.",
    }


def operaciones_ejemplo():
    return pd.DataFrame([
        {
            "nocional_entrada_usd": 10000.0, "nocional_salida_usd": 11000.0,
            "pnl_bruto_usd": 104.2, "coste_total_usd": 4.2,
            "pnl_usd": 100.0, "riesgo_total": 100.0, "R": 1.0,
        },
        {
            "nocional_entrada_usd": 5000.0, "nocional_salida_usd": 6000.0,
            "pnl_bruto_usd": -47.8, "coste_total_usd": 2.2,
            "pnl_usd": -50.0, "riesgo_total": 100.0, "R": -0.5,
        },
    ])


def auditar(plan=None, operaciones=None, huella=None):
    plan = plan_ejemplo() if plan is None else plan
    if huella is None:
        huella = registrar_plan_oos(plan)["plan_sha256"]
    return auditar_costes_plan_oos(
        plan, plan_sha256_esperado=huella,
        operaciones=operaciones_ejemplo() if operaciones is None else operaciones,
    )


def test_costes_dos_lados_y_compromiso_sin_mutaciones():
    plan = plan_ejemplo()
    operaciones = operaciones_ejemplo()
    antes_plan, antes_df = copy.deepcopy(plan), operaciones.copy(deep=True)
    resultado = auditar(plan, operaciones)
    assert resultado["operaciones_auditadas"] == 2
    assert resultado["coste_total_declarado_usd"] == pytest.approx(6.4)
    assert resultado["coste_bps_por_lado"] == 2.0
    assert resultado["plan_sha256"] == registrar_plan_oos(plan)["plan_sha256"]
    assert "no comprueba" in resultado["advertencia"]
    assert plan == antes_plan
    pd.testing.assert_frame_equal(operaciones, antes_df)


def test_rechaza_cambio_de_coste_en_plan_con_huella_previa():
    plan = plan_ejemplo()
    huella = registrar_plan_oos(plan)["plan_sha256"]
    plan["coste_bps_por_lado"] = 3
    with pytest.raises(ValueError, match="huella del plan"):
        auditar(plan, huella=huella)


@pytest.mark.parametrize("campo,valor,mensaje", [
    ("coste_total_usd", 0.0, "Coste declarado incompatible"),
    ("pnl_usd", 101.0, "PnL neto incompatible"),
    ("R", 0.0, "R incompatible"),
    ("nocional_entrada_usd", -100.0, "Nocionales y riesgo"),
    ("riesgo_total", 0.0, "Nocionales y riesgo"),
    ("pnl_bruto_usd", "104.2", "se requieren números"),
    ("coste_total_usd", True, "se requieren números"),
    ("nocional_salida_usd", float("inf"), "no finitos"),
])
def test_rechaza_contabilidad_inconsistente(campo, valor, mensaje):
    operaciones = operaciones_ejemplo()
    # pandas reciente rechaza asignar texto/bool a una columna float64;
    # forzar dtype object solo en el fixture para probar el validador.
    if isinstance(valor, (str, bool)):
        operaciones[campo] = operaciones[campo].astype(object)
    operaciones.at[0, campo] = valor
    with pytest.raises(ValueError, match=mensaje):
        auditar(operaciones=operaciones)


def test_rechaza_columna_ausente_y_huella_invalida():
    with pytest.raises(ValueError, match="Columnas"):
        auditar(operaciones=operaciones_ejemplo().drop(columns=["pnl_bruto_usd"]))
    with pytest.raises(ValueError, match="plan_sha256_esperado"):
        auditar(huella="x" * 64)


def test_permite_bloque_vacio_con_esquema_explicito():
    vacio = operaciones_ejemplo().iloc[0:0]
    resultado = auditar(operaciones=vacio)
    assert resultado["operaciones_auditadas"] == 0
    assert resultado["coste_total_declarado_usd"] == 0.0
