"""Regresiones sintéticas: el manifiesto debe respetar el calendario real."""
import hashlib

import pandas as pd
import pytest

from trading_ia.calendario import minutos_esperados
from trading_ia.manifiesto_local import crear_manifiesto
from trading_ia.reporte_cobertura import crear_reporte_cobertura


def reporte(fecha="2026-01-05", calendario="XNYS"):
    datos = pd.DataFrame({
        "symbol": ["TEST", "TEST"],
        "timestamp": minutos_esperados(fecha, calendario)[:2],
    })
    r = crear_reporte_cobertura(datos, fuente="SINTETICO", calendario=calendario)
    r["archivo_sha256"] = hashlib.sha256(b"solo fixture").hexdigest()
    r["archivo_bytes"] = 12
    return r


def manifiesto(r):
    return crear_manifiesto(
        r, licencia="uso interno", ajuste="sin_ajuste",
        zona_timestamps="UTC", version_dataset="sintetico-v1",
    )


@pytest.mark.parametrize("campo,valor,patron", [
    ("calendario", "OTRO", "Calendario"),
    ("zona_sesion", "UTC", "Zona de sesión"),
    ("inicio", "2026-1-05", "Fecha inicio"),
    ("fin", "2026-01-04", "invertido"),
    ("fin", "2026-01-06", "número de sesiones"),
])
def test_rechaza_metadatos_de_calendario_inconsistentes(campo, valor, patron):
    r = reporte()
    r[campo] = valor
    with pytest.raises(ValueError, match=patron):
        manifiesto(r)


def test_rechaza_fecha_no_bursatil_aun_con_conteos_validos():
    r = reporte()
    r["sesiones"][0]["fecha"] = "2026-01-01"
    with pytest.raises(ValueError, match="fuera del calendario"):
        manifiesto(r)


def test_rechaza_minutos_alterados_aunque_los_totales_cuadren():
    r = reporte()
    # Mutación coordinada que supera las comprobaciones de sumas anteriores.
    for fila in (r["sesiones"][0], r["por_simbolo"][0], r["resumen"]):
        fila["minutos_esperados"] = 389
        fila["minutos_faltantes"] = 387
        fila["fraccion_cobertura"] = round(2 / 389, 6)
    with pytest.raises(ValueError, match="Minutos esperados"):
        manifiesto(r)


def test_rechaza_bandera_y_estado_de_cierre_incoherentes():
    r = reporte()
    r["sesiones"][0]["cierre_anticipado"] = True
    with pytest.raises(ValueError, match="Cierre anticipado"):
        manifiesto(r)
    r = reporte()
    r["sesiones"][0]["estado"] = "completa"
    with pytest.raises(ValueError, match="Estado de sesión"):
        manifiesto(r)


def test_rechaza_totales_de_estado_por_simbolo():
    r = reporte()
    r["por_simbolo"][0]["sesiones_completas"] = 1
    with pytest.raises(ValueError, match="Conteos de estado"):
        manifiesto(r)


def test_acepta_sesion_de_cierre_anticipado_y_xnas():
    r = reporte("2026-11-27", calendario="XNAS")
    assert r["sesiones"][0]["cierre_anticipado"] is True
    m = manifiesto(r)
    assert m["cobertura"]["calendario"] == "XNAS"
    assert m["cobertura"]["inicio"] == "2026-11-27"
