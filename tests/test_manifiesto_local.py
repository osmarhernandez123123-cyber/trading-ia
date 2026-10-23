"""Pruebas sintéticas del manifiesto: no se abren datasets privados."""
import hashlib
import json

import pandas as pd
import pytest

from trading_ia.calendario import minutos_esperados
from trading_ia.manifiesto_local import crear_manifiesto, main
from trading_ia.reporte_cobertura import crear_reporte_cobertura


def reporte_sintetico():
    datos = pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "timestamp": minutos_esperados("2026-01-05")[:2],
    })
    reporte = crear_reporte_cobertura(datos, fuente="IEX")
    reporte["archivo_sha256"] = hashlib.sha256(b"fixture privado no incluido").hexdigest()
    reporte["archivo_bytes"] = 100
    return reporte


def construir(reporte, **cambios):
    argumentos = {
        "licencia": "uso interno autorizado",
        "ajuste": "sin_ajuste",
        "zona_timestamps": "UTC",
        "version_dataset": "iex-2026-01-v1",
        "fuente_esperada": "IEX",
    }
    argumentos.update(cambios)
    return crear_manifiesto(reporte, **argumentos)


def test_manifiesto_declarado_sin_precios_ni_rutas():
    reporte = reporte_sintetico()
    manifiesto = construir(reporte)
    assert manifiesto["archivo_sha256"] == reporte["archivo_sha256"]
    assert manifiesto["archivo_bytes"] == 100
    assert manifiesto["cobertura"]["resumen"] == reporte["resumen"]
    assert manifiesto["version_dataset"] == "iex-2026-01-v1"
    assert "no verificados" in manifiesto["advertencia"]
    serializado = json.dumps(manifiesto)
    assert "precios.csv" not in serializado
    assert "fixture privado" not in serializado


@pytest.mark.parametrize("campo,valor,patron", [
    ("archivo_sha256", "a" * 63, "SHA-256"),
    ("archivo_bytes", -1, "Conteo"),
    ("archivo_bytes", True, "Conteo"),
    ("schema_version", 2, "Versión"),
])
def test_rechaza_integridad_invalida(campo, valor, patron):
    reporte = reporte_sintetico()
    reporte[campo] = valor
    with pytest.raises(ValueError, match=patron):
        construir(reporte)


def test_rechaza_tampering_de_totales_y_sesiones():
    reporte = reporte_sintetico()
    reporte["resumen"]["minutos_presentes"] += 1
    with pytest.raises(ValueError, match="inconsistentes|coinciden"):
        construir(reporte)
    reporte = reporte_sintetico()
    reporte["sesiones"][0]["minutos_presentes"] -= 1
    reporte["sesiones"][0]["minutos_faltantes"] += 1
    reporte["sesiones"][0]["fraccion_cobertura"] = round(1 / 390, 6)
    with pytest.raises(ValueError, match="Sesiones no coinciden"):
        construir(reporte)


def test_rechaza_fuente_licencia_zona_version_y_ajuste_invalidos():
    reporte = reporte_sintetico()
    for cambios, patron in [
        ({"fuente_esperada": "SIP"}, "Fuente"),
        ({"licencia": ""}, "Licencia"),
        ({"zona_timestamps": "Desconocida/Zona"}, "Zona"),
        ({"version_dataset": "../secreto"}, "Versión"),
        ({"ajuste": "sin_especificar"}, "ajuste"),
    ]:
        with pytest.raises(ValueError, match=patron):
            construir(reporte, **cambios)


def test_cli_crea_json_determinista_y_no_sobrescribe(tmp_path):
    reporte = reporte_sintetico()
    origen = tmp_path / "cobertura.json"
    salida = tmp_path / "manifest.json"
    bytes_reporte = (json.dumps(reporte, ensure_ascii=False) + "\n").encode("utf-8")
    origen.write_bytes(bytes_reporte)
    argumentos = [
        "--reporte", str(origen), "--salida", str(salida),
        "--licencia", "uso interno autorizado", "--ajuste", "sin_ajuste",
        "--zona-timestamps", "UTC", "--version-dataset", "iex-2026-01-v1",
        "--fuente-esperada", "IEX",
    ]
    assert main(argumentos) == 0
    manifiesto = json.loads(salida.read_text(encoding="utf-8"))
    assert manifiesto["reporte_cobertura_sha256"] == hashlib.sha256(bytes_reporte).hexdigest()
    assert manifiesto["archivo_sha256"] == reporte["archivo_sha256"]
    anterior = salida.read_bytes()
    with pytest.raises(SystemExit) as exc:
        main(argumentos)
    assert exc.value.code == 2
    assert salida.read_bytes() == anterior
    assert origen.read_bytes() == bytes_reporte


def test_cli_no_sobrescribe_reporte_ni_hardlink(tmp_path):
    origen = tmp_path / "cobertura.json"
    origen.write_text(json.dumps(reporte_sintetico()), encoding="utf-8")
    argumentos = [
        "--reporte", str(origen), "--licencia", "uso interno",
        "--ajuste", "sin_ajuste", "--zona-timestamps", "UTC",
        "--version-dataset", "v1",
    ]
    with pytest.raises(SystemExit) as exc:
        main(argumentos + ["--salida", str(origen)])
    assert exc.value.code == 2
    alias = tmp_path / "alias.json"
    alias.hardlink_to(origen)
    with pytest.raises(SystemExit) as exc:
        main(argumentos + ["--salida", str(alias)])
    assert exc.value.code == 2
