from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import backtesting_v3_1 as bt
from trading_ia.calendario import minutos_esperados


DAY = "2026-01-05"


def ts(hhmm, day=DAY):
    return pd.Timestamp(f"{day} {hhmm}:00", tz="America/New_York").tz_convert("UTC")


def bar(symbol, hhmm, open_, high, low, close, day=DAY):
    return {
        "symbol": symbol,
        "timestamp": ts(hhmm, day),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1_000,
    }


def candidate(symbol, direction, entry_hhmm="09:31", entry=100.0, distance=1.0, day=DAY):
    sign = 1 if direction == "LONG" else -1
    return {
        "symbol": symbol,
        "timestamp": ts("09:30", day),
        "entrada_timestamp": ts(entry_hhmm, day),
        "SENAL": direction,
        "entrada_precio": entry,
        "distancia_sl": distance,
        "stop_loss": entry - sign * distance,
        "take_profit": entry + sign * 2 * distance,
    }


@pytest.fixture
def run_backtest(tmp_path, monkeypatch):
    def run(velas, candidatas, strict=False, **constants):
        paths = {
            "VELAS": tmp_path / "velas.parquet",
            "CANDIDATAS": tmp_path / "candidatas.parquet",
            "SALIDA": tmp_path / "resultados.parquet",
            "RECHAZOS": tmp_path / "rechazos.parquet",
            "CURVA": tmp_path / "curva.parquet",
        }
        for name, path in paths.items():
            monkeypatch.setattr(bt, name, Path(path))
        for name, value in constants.items():
            monkeypatch.setattr(bt, name, value)
        pd.DataFrame(velas).to_parquet(paths["VELAS"], index=False)
        pd.DataFrame(candidatas).to_parquet(paths["CANDIDATAS"], index=False)
        bt.ejecutar(exigir_calidad=strict)
        return (
            pd.read_parquet(paths["SALIDA"]),
            pd.read_parquet(paths["RECHAZOS"]),
            pd.read_parquet(paths["CURVA"]),
        )

    return run


@pytest.mark.parametrize(
    ("direction", "touch", "expected_reason"),
    [
        ("LONG", dict(open_=100, high=102.2, low=100, close=102), "TAKE_PROFIT_ENTRADA"),
        ("SHORT", dict(open_=100, high=100, low=97.8, close=98), "TAKE_PROFIT_ENTRADA"),
        ("LONG", dict(open_=100, high=100, low=98.8, close=99), "STOP_LOSS_ENTRADA"),
        ("SHORT", dict(open_=100, high=101.2, low=100, close=101), "STOP_LOSS_ENTRADA"),
    ],
)
def test_long_short_stop_and_target(run_backtest, direction, touch, expected_reason):
    velas = [
        bar("AAPL", "09:30", 100, 100, 100, 100),
        bar("AAPL", "09:31", **touch),
        bar("AAPL", "09:32", 100, 100, 100, 100),
    ]
    result, _, _ = run_backtest(velas, [candidate("AAPL", direction)])
    assert result.loc[0, "motivo_salida"] == expected_reason
    assert (result.loc[0, "R"] > 0) == ("TAKE_PROFIT" in expected_reason)


def test_gap_stop_uses_open_and_can_lose_more_than_one_r(run_backtest):
    velas = [
        bar("AAPL", "09:30", 100, 100, 100, 100),
        bar("AAPL", "09:31", 100, 100.2, 99.8, 100),
        bar("AAPL", "09:32", 97, 98, 96, 97),
        bar("AAPL", "09:33", 97, 97, 97, 97),
    ]
    result, _, _ = run_backtest(velas, [candidate("AAPL", "LONG")])
    assert result.loc[0, "motivo_salida"] == "GAP_STOP"
    assert result.loc[0, "salida"] == pytest.approx(97 * (1 - bt.SLIPPAGE_BPS / 10_000))
    assert result.loc[0, "R"] < -1


def test_same_bar_stop_and_target_prefers_stop(run_backtest):
    velas = [
        bar("AAPL", "09:30", 100, 100, 100, 100),
        bar("AAPL", "09:31", 100, 103, 98, 100),
        bar("AAPL", "09:32", 100, 100, 100, 100),
    ]
    result, _, _ = run_backtest(velas, [candidate("AAPL", "LONG")])
    assert result.loc[0, "motivo_salida"] == "STOP_LOSS_ENTRADA"


def test_nominal_two_r_is_lower_after_adverse_slippage(run_backtest):
    velas = [
        bar("AAPL", "09:30", 100, 100, 100, 100),
        bar("AAPL", "09:31", 100, 102.2, 99.9, 102),
        bar("AAPL", "09:32", 102, 102, 102, 102),
    ]
    result, _, _ = run_backtest(velas, [candidate("AAPL", "LONG")])
    trade = result.iloc[0]
    assert trade.R_objetivo_nominal == pytest.approx(2.0)
    assert trade.R == pytest.approx(trade.R_objetivo_ejecutable)
    assert trade.R_objetivo_ejecutable < 2.0


def test_risk_size_and_cumulative_capital(run_backtest):
    velas = [
        bar("AAPL", "09:30", 100, 100, 100, 100),
        bar("AAPL", "09:31", 100, 103, 99.9, 102),
        bar("AAPL", "09:32", 102, 102, 102, 102),
        bar("MSFT", "09:30", 100, 100, 100, 100),
        bar("MSFT", "09:31", 100, 100.1, 98.8, 99),
        bar("MSFT", "09:32", 99, 99, 99, 99),
    ]
    candidates = [candidate("AAPL", "LONG"), candidate("MSFT", "LONG")]
    result, _, curve = run_backtest(velas, candidates)
    assert (result.riesgo_total <= result.patrimonio_entrada * bt.RIESGO_OPERACION + bt.TOL).all()
    assert result.acciones.map(lambda x: float(x).is_integer()).all()
    assert result.iloc[-1].capital_cierre == pytest.approx(bt.CAPITAL_INICIAL + result.pnl_usd.sum())
    assert curve.riesgo_abierto.max() <= bt.CAPITAL_INICIAL * bt.RIESGO_TOTAL + bt.TOL


def test_incomplete_session_closes_at_last_observation(run_backtest):
    velas = [
        bar("AAPL", "09:30", 100, 100, 100, 100),
        bar("AAPL", "09:31", 100, 100.5, 99.8, 100.2),
        bar("AAPL", "09:32", 100.2, 100.6, 100.0, 100.4),
    ]
    result, _, _ = run_backtest(velas, [candidate("AAPL", "LONG")])
    assert result.loc[0, "motivo_salida"] == "FIN_SESION_DATOS_INCOMPLETOS"
    assert result.loc[0, "salida_timestamp"] == ts("09:32")


def test_strict_mode_blocks_incomplete_data_before_backtest(run_backtest):
    velas = [
        bar("AAPL", "09:30", 100, 100, 100, 100),
        bar("AAPL", "09:31", 100, 100.5, 99.8, 100.2),
        bar("AAPL", "09:32", 100.2, 100.6, 100.0, 100.4),
    ]
    with pytest.raises(ValueError, match="HUECOS_DE_SESION"):
        run_backtest(velas, [candidate("AAPL", "LONG")], strict=True)


def test_official_early_close_is_not_marked_as_missing_data(run_backtest):
    day = "2026-11-27"
    velas = [{
        "symbol": "AAPL", "timestamp": timestamp,
        "open": 100, "high": 100.4, "low": 99.8, "close": 100.2,
        "volume": 1_000,
    } for timestamp in minutos_esperados(day)]
    candidata = candidate("AAPL", "LONG", entry_hhmm="12:58", distance=1, day=day)
    candidata["timestamp"] = ts("12:57", day)
    result, _, _ = run_backtest(velas, [candidata], strict=True)
    assert result.loc[0, "motivo_salida"] == "FIN_SESION"
    assert result.loc[0, "salida_timestamp"] == ts("12:59", day)


def test_strict_backtest_rejects_original_row_outside_regular_session(run_backtest):
    day = "2026-11-27"
    velas = [{
        "symbol": "AAPL", "timestamp": timestamp,
        "open": 100, "high": 100.4, "low": 99.8, "close": 100.2,
        "volume": 1_000,
    } for timestamp in minutos_esperados(day)]
    velas.append(bar("AAPL", "08:00", 100, 101, 99, 100, day))
    candidata = candidate("AAPL", "LONG", entry_hhmm="12:58", distance=1, day=day)
    candidata["timestamp"] = ts("12:57", day)
    with pytest.raises(ValueError, match="TIMESTAMP_NO_PERMITIDO"):
        run_backtest(velas, [candidata], strict=True)


def test_three_simultaneous_positions_and_fourth_rejected(run_backtest):
    symbols = ["AAPL", "MSFT", "NVDA", "TSLA"]
    velas = []
    candidatas = []
    for symbol in symbols:
        velas.extend([
            bar(symbol, "09:30", 100, 100, 100, 100),
            bar(symbol, "09:31", 100, 100.5, 99.5, 100),
            bar(symbol, "09:32", 100, 100.5, 99.5, 100),
        ])
        candidatas.append(candidate(symbol, "LONG", distance=10))
    result, rejections, curve = run_backtest(velas, candidatas)
    assert set(result.symbol) == {"AAPL", "MSFT", "NVDA"}
    rechazo = rejections.loc[rejections.symbol == "TSLA"].iloc[0]
    assert rechazo.motivo == "MAX_POSICIONES"
    assert curve.posiciones_abiertas.max() == 3
    assert curve.riesgo_abierto.max() <= bt.CAPITAL_INICIAL * bt.RIESGO_TOTAL + bt.TOL


@pytest.mark.parametrize(
    "bad_value",
    [np.nan, np.inf, -1.0],
)
def test_invalid_or_missing_ohlc_is_rejected(run_backtest, bad_value):
    velas = [
        bar("AAPL", "09:30", 100, 100, 100, 100),
        bar("AAPL", "09:31", bad_value, 101, 99, 100),
    ]
    with pytest.raises(ValueError, match="OHLC"):
        run_backtest(velas, [candidate("AAPL", "LONG")])
