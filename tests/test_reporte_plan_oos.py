"""Pruebas sintéticas del vínculo plan -> reporte; sin red ni broker."""
import copy
from datetime import date

import exchange_calendars as xcals
import pandas as pd
import pytest

from trading_ia.registro_plan_oos import registrar_plan_oos
from trading_ia.reporte_plan_oos import comparar_plan_registrado_oos


def sesiones_ejemplo():
    # Fechas reales XNYS, operaciones completamente sintéticas.
    mercado = xcals.get_calendar("XNYS")
    return [ts.date() for ts in mercado.sessions_in_range("2026-01-02", "2026-01-23")]


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


def bloques_ejemplo(pnl, fechas=None):
    fechas = sesiones_ejemplo() if fechas is None else fechas
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


def ejecutar(plan=None, *, huella=None, base=None, candidata=None, sesiones=None,
            auditar_costes=False):
    plan = plan_ejemplo() if plan is None else plan
    if huella is None:
        huella = registrar_plan_oos(plan)["plan_sha256"]
    return comparar_plan_registrado_oos(
        plan, plan_sha256_esperado=huella,
        sesiones=sesiones_ejemplo() if sesiones is None else sesiones,
        baseline_por_ventana=bloques_ejemplo(100) if base is None else base,
        candidata_por_ventana=bloques_ejemplo(50) if candidata is None else candidata,
        auditar_costes=auditar_costes,
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
        comparar_plan_registrado_oos(
            plan_ejemplo(), plan_sha256_esperado=huella,
            sesiones=sesiones_ejemplo(),
            baseline_por_ventana=bloques_ejemplo(100),
            candidata_por_ventana=bloques_ejemplo(50),
        )


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


@pytest.mark.parametrize("indice,fecha", [
    (1, date(2026, 1, 3)),   # Sábado entre dos sesiones válidas
    (11, date(2026, 1, 19)), # Festivo bursátil estadounidense
])
def test_rechaza_dias_no_bursatiles_aunque_estan_ordenados(indice, fecha):
    sesiones = sesiones_ejemplo()
    sesiones[indice] = fecha
    with pytest.raises(ValueError, match="calendario XNYS"):
        ejecutar(sesiones=sesiones)


def test_rechaza_sesion_faltante_aunque_fechas_restantes_sean_validas():
    sesiones = sesiones_ejemplo()
    sesiones.pop(7)
    with pytest.raises(ValueError, match="calendario XNYS"):
        ejecutar(sesiones=sesiones)


def test_acepta_15_sesiones_reales_xnys_con_feriado_intermedio():
    resultado = ejecutar()
    assert resultado["comparacion"]["baseline"]["operaciones"] == 3
    assert resultado["plan"]["fin_prueba"] == date(2026, 1, 23).isoformat()


@pytest.mark.parametrize("campo,hora", [
    ("entrada_timestamp", "09:29"),  # Antes de la apertura regular.
    ("entrada_timestamp", "16:00"),  # No iniciar al cierre.
    ("salida_timestamp", "16:01"),   # Después del cierre.
])
def test_rechaza_operaciones_fuera_de_horario_regular_xnys(campo, hora):
    base = bloques_ejemplo(100)
    dia = base[0].loc[0, "entrada_timestamp"].date()
    base[0].loc[0, campo] = pd.Timestamp(
        f"{dia.isoformat()} {hora}", tz="America/New_York"
    )
    with pytest.raises(ValueError, match="horario regular XNYS"):
        ejecutar(base=base)


def _caso_cierre_anticipado():
    mercado = xcals.get_calendar("XNYS")
    fechas = [
        ts.date() for ts in mercado.sessions_in_range(
            "2026-11-10", "2026-12-01"
        )
    ]
    assert len(fechas) == 15
    assert fechas[12] == date(2026, 11, 27)  # Día después de Thanksgiving.
    assert mercado.session_close(pd.Timestamp(fechas[12])).tz_convert(
        "America/New_York"
    ).hour == 13
    plan = plan_ejemplo()
    plan["inicio_prueba"] = fechas[9].isoformat()
    plan["fin_prueba"] = fechas[14].isoformat()
    return plan, fechas, bloques_ejemplo(100, fechas), bloques_ejemplo(50, fechas)


def test_rechaza_entrada_despues_de_cierre_anticipado():
    plan, fechas, base, candidata = _caso_cierre_anticipado()
    base[1].loc[0, "entrada_timestamp"] = pd.Timestamp(
        "2026-11-27 13:01", tz="America/New_York"
    )
    base[1].loc[0, "salida_timestamp"] = pd.Timestamp(
        "2026-11-27 13:02", tz="America/New_York"
    )
    with pytest.raises(ValueError, match="horario regular XNYS"):
        ejecutar(plan, sesiones=fechas, base=base, candidata=candidata)


def test_acepta_salida_exacta_al_cierre_anticipado():
    plan, fechas, base, candidata = _caso_cierre_anticipado()
    base[1].loc[0, "entrada_timestamp"] = pd.Timestamp(
        "2026-11-27 12:55", tz="America/New_York"
    )
    base[1].loc[0, "salida_timestamp"] = pd.Timestamp(
        "2026-11-27 13:00", tz="America/New_York"
    )
    resultado = ejecutar(plan, sesiones=fechas, base=base, candidata=candidata)
    assert resultado["comparacion"]["baseline"]["operaciones"] == 3


def bloques_con_costes(pnl):
    """Costes y nocionales sintéticos compatibles con 2 bps por lado."""
    bloques = bloques_ejemplo(pnl)
    for bloque in bloques:
        bloque["nocional_entrada_usd"] = 10_000.0
        bloque["nocional_salida_usd"] = 10_000.0
        bloque["pnl_bruto_usd"] = float(pnl) + 4.0
        bloque["coste_total_usd"] = 4.0
    return bloques


def test_auditoria_costes_optin_y_salida_compatible_sin_ella():
    assert "auditoria_costes" not in ejecutar()
    base, candidata = bloques_con_costes(100), bloques_con_costes(50)
    antes = [bloque.copy(deep=True) for bloque in base]
    resultado = ejecutar(base=base, candidata=candidata, auditar_costes=True)
    auditoria = resultado["auditoria_costes"]
    assert auditoria["plan_sha256"] == resultado["plan_sha256"]
    assert auditoria["coste_bps_por_lado"] == 2.0
    assert auditoria["baseline"]["operaciones_auditadas"] == 3
    assert auditoria["baseline"]["coste_total_declarado_usd"] == pytest.approx(12.0)
    assert auditoria["candidata"]["coste_total_declarado_usd"] == pytest.approx(12.0)
    assert len(auditoria["baseline"]["por_ventana"]) == 3
    assert "no comprueba" in auditoria["advertencia"]
    for bloque, original in zip(base, antes):
        pd.testing.assert_frame_equal(bloque, original)


def test_auditoria_costes_optin_falla_ante_coste_incoherente():
    base = bloques_con_costes(100)
    base[0].loc[0, "coste_total_usd"] = 0.0
    with pytest.raises(ValueError, match="baseline bloque 1: auditoría de costes: Coste declarado"):
        ejecutar(base=base, candidata=bloques_con_costes(50), auditar_costes=True)


def test_auditoria_costes_optin_rechaza_campos_ausentes_sin_inferirlos():
    with pytest.raises(ValueError, match="auditoría de costes: Columnas"):
        ejecutar(auditar_costes=True)


def test_auditoria_costes_exige_flag_booleano():
    with pytest.raises(ValueError, match="auditar_costes debe ser booleano"):
        ejecutar(auditar_costes="si")
