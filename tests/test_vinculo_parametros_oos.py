"""Verificación sintética de parámetros OOS, sin archivos privados ni red."""
import copy
import hashlib

import pytest

from trading_ia.registro_plan_oos import registrar_plan_oos
from trading_ia.vinculo_parametros_oos import verificar_parametros_oos


BASE = b'{"ema_rapida":9,"ema_lenta":21,"riesgo":0.01}'
CANDIDATA = b'{"ema_rapida":8,"ema_lenta":21,"riesgo":0.01}'


def plan_ejemplo():
    return {
        "schema_version": 1,
        "dataset_sha256": "a" * 64,
        "baseline_id": "V3.1",
        "candidata_id": "candidata",
        "baseline_parametros_sha256": hashlib.sha256(BASE).hexdigest(),
        "candidata_parametros_sha256": hashlib.sha256(CANDIDATA).hexdigest(),
        "universo": ["AAPL"],
        "inicio_prueba": "2026-01-05",
        "fin_prueba": "2026-02-05",
        "coste_bps_por_lado": 2.0,
        "ventanas": {
            "entrenamiento": 10, "validacion": 5, "prueba": 3,
            "embargo": 2, "horizonte_etiqueta": 2, "paso": 3,
        },
        "hipotesis": "La candidata no supera al baseline.",
    }


def verificar(plan=None, *, base=BASE, candidata=CANDIDATA, esperado=None):
    plan = plan_ejemplo() if plan is None else plan
    esperado = registrar_plan_oos(plan)["plan_sha256"] if esperado is None else esperado
    return verificar_parametros_oos(
        plan, plan_sha256_esperado=esperado,
        baseline_bytes=base, candidata_bytes=candidata,
    )


def test_coincidencia_de_bytes_sinteticos_y_entrada_inmutable():
    plan = plan_ejemplo()
    original = copy.deepcopy(plan)
    resultado = verificar(plan)
    assert resultado["plan_sha256"] == registrar_plan_oos(plan)["plan_sha256"]
    assert resultado["baseline_parametros_sha256"] == hashlib.sha256(BASE).hexdigest()
    assert resultado["candidata_parametros_sha256"] == hashlib.sha256(CANDIDATA).hexdigest()
    assert resultado["baseline_parametros_bytes"] == len(BASE)
    assert resultado["candidata_parametros_bytes"] == len(CANDIDATA)
    assert "ema_rapida" not in str(resultado)
    assert plan == original


@pytest.mark.parametrize("campo,contenido", [
    ("base", BASE + b" "),
    ("candidata", CANDIDATA.replace(b"8", b"7")),
])
def test_rechaza_configuracion_modificada_aunque_sea_semanticamente_similar(campo, contenido):
    argumentos = {campo: contenido}
    with pytest.raises(ValueError, match="SHA-256 distinto"):
        verificar(**argumentos)


def test_rechaza_plan_modificado_aunque_hashes_de_archivos_coincidan():
    plan = plan_ejemplo()
    compromiso = registrar_plan_oos(plan)["plan_sha256"]
    plan["coste_bps_por_lado"] = 3
    with pytest.raises(ValueError, match="compromiso externo"):
        verificar(plan, esperado=compromiso)


@pytest.mark.parametrize("valor", ["A" * 64, "a" * 63, None, 123, True])
def test_rechaza_compromiso_no_canonico(valor):
    with pytest.raises(ValueError, match="plan_sha256_esperado"):
        verificar(esperado=valor)


@pytest.mark.parametrize("valor", [b"", b"x" * (1024 * 1024 + 1), "texto", bytearray(b"x"), None])
def test_rechaza_contenido_invalido_o_excesivo(valor):
    with pytest.raises(ValueError, match="bytes no vacíos"):
        verificar(base=valor)


def test_no_admite_plan_con_hashes_inventados():
    plan = plan_ejemplo()
    plan["candidata_parametros_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256 distinto"):
        verificar(plan)
