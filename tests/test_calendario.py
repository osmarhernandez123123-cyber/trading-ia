import pandas as pd

from trading_ia.calendario import (
    anotar_sesion,
    clasificar_cobertura,
    horario_sesiones,
    minutos_esperados,
)


def test_festivo_no_es_sesion_y_timestamp_es_rechazado():
    horario = horario_sesiones("2026-07-03", "2026-07-03")
    assert horario.empty  # Independence Day observado
    timestamp = pd.Timestamp("2026-07-03 14:30", tz="UTC")
    fila = anotar_sesion([timestamp]).iloc[0]
    assert not fila.es_sesion
    assert not fila.en_horario


def test_cierre_anticipado_tiene_210_velas_y_no_es_dato_incompleto():
    fecha = "2026-11-27"  # viernes posterior a Thanksgiving
    minutos = minutos_esperados(fecha)
    cobertura = clasificar_cobertura(minutos)
    assert len(minutos) == 210
    assert minutos[-1].tz_convert("America/New_York").strftime("%H:%M") == "12:59"
    assert cobertura.loc[0, "estado"] == "completa_cierre_anticipado"
    assert cobertura.loc[0, "minutos_faltantes"] == 0


def test_sesion_truncada_se_distingue_de_cierre_anticipado():
    minutos = minutos_esperados("2026-11-27")[:-1]
    cobertura = clasificar_cobertura(minutos, "2026-11-27", "2026-11-27")
    assert cobertura.loc[0, "cierre_anticipado"]
    assert cobertura.loc[0, "estado"] == "incompleta"
    assert cobertura.loc[0, "minutos_faltantes"] == 1


def test_dst_cambia_utc_pero_conserva_apertura_local():
    antes = horario_sesiones("2026-03-06", "2026-03-06").iloc[0]
    despues = horario_sesiones("2026-03-09", "2026-03-09").iloc[0]
    assert antes.open.hour == 14
    assert despues.open.hour == 13
    assert antes.open.tz_convert("America/New_York").strftime("%H:%M") == "09:30"
    assert despues.open.tz_convert("America/New_York").strftime("%H:%M") == "09:30"


def test_nyse_y_nasdaq_comparten_horario_regular_del_universo_actual():
    nyse = horario_sesiones("2026-11-27", "2026-11-27", "XNYS")
    nasdaq = horario_sesiones("2026-11-27", "2026-11-27", "XNAS")
    pd.testing.assert_series_equal(nyse["open"], nasdaq["open"])
    pd.testing.assert_series_equal(nyse["close"], nasdaq["close"])
