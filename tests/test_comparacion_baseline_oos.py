"""Pruebas de comparación OOS: solo datos sintéticos y sin broker."""
from datetime import date, timedelta

import pandas as pd
import pytest

from trading_ia.comparacion_baseline_oos import comparar_baseline_oos
from trading_ia.validacion_temporal import crear_ventanas


def ventanas():
    sesiones = [date(2026, 1, 1) + timedelta(days=i) for i in range(15)]
    return crear_ventanas(
        sesiones, entrenamiento=3, validacion=2, prueba=2, embargo=1
    )[:2]


def trade(dia, pnl, minuto=30):
    return dict(
        symbol="TEST",
        entrada_timestamp=f"2026-01-{dia:02d}T15:{minuto:02d}:00Z",
        salida_timestamp=f"2026-01-{dia:02d}T15:{minuto + 1:02d}:00Z",
        pnl_usd=float(pnl), riesgo_total=100.0, R=float(pnl / 100),
    )


def bloques():
    baseline = [
        pd.DataFrame([trade(8, 100), trade(9, -100)]),
        pd.DataFrame([trade(10, 100)]),
    ]
    candidata = [
        pd.DataFrame([trade(8, 150), trade(9, -50)]),
        pd.DataFrame([trade(10, -100)]),
    ]
    return baseline, candidata


def comparar(v, base, candidata):
    return comparar_baseline_oos(
        v, base, candidata,
        id_baseline="V3.1 fijo", id_candidata="Alternativa fija",
    )


def test_compara_mismas_ventanas_sin_ranking_ni_p_valores():
    v = ventanas()
    b, c = bloques()
    copias = [df.copy(deep=True) for df in b + c]
    r = comparar(v, b, c)
    assert r["baseline"]["operaciones"] == 3
    assert r["candidata"]["operaciones"] == 3
    assert r["baseline"]["expectativa_r_ponderada"] == pytest.approx(1 / 3)
    assert r["candidata"]["expectativa_r_ponderada"] == pytest.approx(0.0)
    assert r["por_ventana"][0]["diferencia_media_r_descriptiva"] == pytest.approx(0.5)
    assert r["por_ventana"][1]["diferencia_media_r_descriptiva"] == pytest.approx(-2.0)
    assert "rank" not in r and "p_value" not in r
    assert "no prueba de superioridad" in r["advertencia"]
    for original, despues in zip(copias, b + c):
        pd.testing.assert_frame_equal(original, despues)


def test_sin_trades_no_inventa_media_r_cero():
    v = ventanas()
    b, c = bloques()
    b[1] = b[1].iloc[:0].copy()
    r = comparar(v, b, c)
    assert r["por_ventana"][1]["expectativa_r_baseline"] is None
    assert r["por_ventana"][1]["diferencia_media_r_descriptiva"] is None


def test_rechaza_ventanas_o_bloques_inconsistentes():
    v = ventanas()
    b, c = bloques()
    with pytest.raises(ValueError, match="pareados"):
        comparar(v, b, c[:1])
    with pytest.raises(ValueError, match="solapadas"):
        comparar([v[0], v[0]], b, c)
    with pytest.raises(ValueError, match="fuera del bloque"):
        comparar(v, b, [c[1], c[0]])


def test_rechaza_datos_no_validos_en_cualquiera_de_los_modelos():
    v = ventanas()
    b, c = bloques()
    c[0].loc[0, "R"] = 999
    with pytest.raises(ValueError, match="no coincide"):
        comparar(v, b, c)
    b, c = bloques()
    b[0].loc[0, "entrada_timestamp"] = "2026-01-08 15:30:00"
    with pytest.raises(ValueError, match="zona horaria"):
        comparar(v, b, c)


@pytest.mark.parametrize("base_id,candidata_id", [
    ("", "alternativa"), ("V3.1", "V3.1"), ("  ", "alternativa"),
    ("V3.1", None), (None, "alternativa"),
])
def test_rechaza_identificadores_ambiguos(base_id, candidata_id):
    b, c = bloques()
    with pytest.raises(ValueError, match="identificadores"):
        comparar_baseline_oos(
            ventanas(), b, c, id_baseline=base_id, id_candidata=candidata_id
        )


def test_capital_inicial_debe_ser_valido_para_ambos():
    b, c = bloques()
    with pytest.raises(ValueError, match="capital_inicial"):
        comparar_baseline_oos(
            ventanas(), b, c, id_baseline="a", id_candidata="b",
            capital_inicial=float("nan"),
        )
