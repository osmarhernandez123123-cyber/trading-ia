"""Pruebas sintéticas del vínculo plan -> reporte; sin red ni broker."""
import copy
from datetime import date, timedelta

import pandas as pd
import pytest

from trading_ia.registro_plan_oos import registrar_plan_oos
from trading_ia.reporte_plan_oos import comparar_plan_registrado_oos


def sesiones_ejemplo():
    # Días artificiales para probar índices; NO calendario bursátil real.
    return [date(2026, 1, 1) + timedelta(days=i) for i in range(15)]


def plan_ejemplo():
    fechas = sesiones_ejemplo()
    return {
        "schema_version": 1,
        "dataset_sha256": "a" * 64,
        "baseline_id": "V3.1",
        "candidata_id": "modelo-B",
        "baseline_parametros_sha256": "b" * 64,
        "candidata_parametros_sha256": "c" * 64,
        "universo": ["MSFT", "AAPL"],
        "inicio_prueba": fechas[9].isoformat(),
        "fin_prueba": fechas[14].isoformat(),
        "coste_bps_por_lado": 2,
        "ventanas": {
            "entrenamiento": 5, "validacion": 2, "prueba": 2,
            "embargo": 1, "horizonte_etiqueta": 1, "paso": 2,
        },
        "hipotesis": "No se presupone superioridad de la candidata.",
    }


def bloques_ejemplo(pnl):
    fechas = sesiones_ejemplo()
    bloques = []
    for i in (9, 11, 13):
        entrada = pd.Timestamp(f"{fechas[i].isoformat()} 10:00", tz="America/New_York")
        salida = entrada + pd.Timedelta(minutes=5)
        bloques.append(pd.DataFrame([{
            "symbol": "AAPL",
            "entrada_timestamp": entrada,
            "salida_timestamp": salida,
            "pnl_usd": pnl,
            "riesgo_total": 100.0,
            "R": pnl / 100.0,
        }]))
    return bloques


def ejecutar(plan=None, *, huella=None, base=None, candidata=None, sesiones=None):
    plan = plan_ejemplo() if plan is None else plan
    if huella is None:
        huella = registrar_plan_oos(plan)["plan_sha256"]
    return comparar_plan_registrado_oos(
        plan, plan_sha256_esperado=huella,
        sesiones=sesiones_ejemplo() if sesiones is None else sesiones,
        baseline_por_ventana=bloques_ejemplo(100) if base is None else base,
        candidata_por_ventana=bloques_ejemplo(50) if candidata is None else candidata,
    )


def test_reporte_reproduce_plan_y_comparacion_sin_mutar_entradas():
    plan = plan_ejemplo()
    antes = copy.deepcopy(plan)
    resultado = ejecutar(plan)
    assert plan == antes
    assert resultado["plan_sha256"] == registrar_plan_oos(plan)["plan_sha256"]
    assert resultado["plan"]["universo"] == ["AAPL", "MSFT"]
    assert resultado["comparacion"]["id_baseline"] == "V3.1"
    assert resultado["comparacion"]["id_candidata"] == "modelo-B"
    assert resultado["comparacion"]["baseline"]["operaciones"] == 3
    assert resultado["comparacion"]["candidata"]["operaciones"] == 3
    assert all(
        item["diferencia_media_r_descriptiva"] == -0.5
        for item in resultado["comparacion"]["por_ventana"]
    )
    assert ejecutar(plan) == resultado
    assert "no acredita fecha" in resultado["advertencia"]


def test_rechaza_modificacion_de_plan_con_compromiso_original():
    plan = plan_ejemplo()
    original = registrar_plan_oos(plan)["plan_sha256"]
    plan["candidata_parametros_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="huella del plan"):
        ejecutar(plan, huella=original)


@pytest.mark.parametrize("huella", ["A" * 64, "0" * 63, "", None])
def test_rechaza_huella_ambigua(huella):
    with pytest.raises(ValueError, match="plan_sha256_esperado"):
        ejecutar(huella=huella)


def test_rechaza_limites_oos_aunque_plan_tenga_huella_valida():
    plan = plan_ejemplo()
    plan["fin_prueba"] = "2026-01-16"
    with pytest.raises(ValueError, match="límites OOS"):
        ejecutar(plan)


def test_rechaza_configuracion_distinta_de_ventanas():
    plan = plan_ejemplo()
    plan["ventanas"]["paso"] = 3
    with pytest.raises(ValueError, match="límites OOS|Cantidad de bloques"):
        ejecutar(plan)


def test_rechaza_simbolo_fuera_del_universo():
    candidata = bloques_ejemplo(50)
    candidata[0].loc[0, "symbol"] = "NVDA"
    with pytest.raises(ValueError, match="universo registrado"):
        ejecutar(candidata=candidata)


def test_rechaza_bloques_faltantes():
    with pytest.raises(ValueError, match="Cantidad de bloques"):
        ejecutar(base=bloques_ejemplo(100)[:2])


def test_rechaza_operaciones_fuera_de_la_ventana():
    base = bloques_ejemplo(100)
    base[0].loc[0, "entrada_timestamp"] = pd.Timestamp(
        "2026-01-09 10:00", tz="America/New_York"
    )
    with pytest.raises(ValueError, match="fuera del bloque de prueba"):
        ejecutar(base=base)


def test_rechaza_sesiones_no_ordenadas():
    sesiones = sesiones_ejemplo()
    sesiones[2], sesiones[3] = sesiones[3], sesiones[2]
    with pytest.raises(ValueError, match="ordenada"):
        ejecutar(sesiones=sesiones)


def test_rechaza_bloque_sin_esquema():
    base = bloques_ejemplo(100)
    base[0] = pd.DataFrame([{"pnl_usd": 100}])
    with pytest.raises(ValueError, match="bloque de operaciones inválido"):
        ejecutar(base=base)
