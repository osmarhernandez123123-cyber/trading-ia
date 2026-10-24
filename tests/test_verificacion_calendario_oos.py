"""Pruebas de calendario XNYS sobre fechas sintéticas; sin datos ni órdenes."""
import hashlib
import json

import pytest

from trading_ia.registro_plan_oos import registrar_plan_oos
from trading_ia.verificacion_artefacto_oos import main, verificar_artefacto_oos


def _artefacto(*, paso=4, inicio="2026-01-05", fin="2026-01-13"):
    plan = {
        "schema_version": 1,
        "dataset_sha256": "a" * 64,
        "baseline_id": "V3.1",
        "candidata_id": "candidata-sintetica",
        "baseline_parametros_sha256": "b" * 64,
        "candidata_parametros_sha256": "c" * 64,
        "universo": ["AAPL"],
        "inicio_prueba": inicio,
        "fin_prueba": fin,
        "coste_bps_por_lado": 2.0,
        "ventanas": {
            "entrenamiento": 10, "validacion": 5, "prueba": 3,
            "embargo": 2, "horizonte_etiqueta": 2, "paso": paso,
        },
        "hipotesis": "Solo estructura sintética de sesiones.",
    }
    registro = registrar_plan_oos(plan)
    limites = [(inicio, "2026-01-07"), ("2026-01-09", fin)]
    def bloques():
        return [
            {"inicio_prueba": a, "fin_prueba": b,
             "operaciones": 0, "expectativa_r": None}
            for a, b in limites
        ]
    reporte = {
        "schema_version": 1,
        "plan_sha256": registro["plan_sha256"],
        "plan": registro["plan"],
        "comparacion": {
            "schema_version": 1,
            "id_baseline": "V3.1",
            "id_candidata": "candidata-sintetica",
            "baseline": {"ventanas": 2, "operaciones": 0, "por_ventana": bloques()},
            "candidata": {"ventanas": 2, "operaciones": 0, "por_ventana": bloques()},
            "por_ventana": [
                {"inicio_prueba": a, "fin_prueba": b,
                 "operaciones_baseline": 0, "operaciones_candidata": 0,
                 "expectativa_r_baseline": None, "expectativa_r_candidata": None,
                 "diferencia_media_r_descriptiva": None}
                for a, b in limites
            ],
        },
    }
    contenido = json.dumps(reporte, sort_keys=True, ensure_ascii=False).encode("utf-8")
    referencias = {
        "reporte_sha256_esperado": hashlib.sha256(contenido).hexdigest(),
        "plan_sha256_esperado": registro["plan_sha256"],
        "dataset_sha256_esperado": "a" * 64,
    }
    return contenido, referencias


def test_acepta_dos_ventanas_xnys_con_paso_y_festivos_reales():
    contenido, referencias = _artefacto()
    resultado = verificar_artefacto_oos(
        contenido, **referencias, verificar_calendario=True,
    )
    assert resultado["calendario_xnys_verificado"] is True
    assert verificar_artefacto_oos(
        contenido, **referencias,
    )["calendario_xnys_verificado"] is False


def test_rechaza_paso_incompatible_aunque_huellas_sean_consistentes():
    contenido, referencias = _artefacto(paso=3)
    # El reporte y el plan coinciden entre sí, pero el salto real es de 4 sesiones.
    assert verificar_artefacto_oos(contenido, **referencias)["schema_version"] == 1
    with pytest.raises(ValueError, match="avance de sesiones"):
        verificar_artefacto_oos(
            contenido, **referencias, verificar_calendario=True,
        )


def test_rechaza_longitud_de_prueba_falsa_aunque_resumenes_coincidan():
    contenido, referencias = _artefacto()
    reporte = json.loads(contenido)
    for nombre in ("baseline", "candidata"):
        reporte["comparacion"][nombre]["por_ventana"][0]["fin_prueba"] = "2026-01-08"
    reporte["comparacion"]["por_ventana"][0]["fin_prueba"] = "2026-01-08"
    cambiado = json.dumps(reporte, sort_keys=True).encode()
    referencias["reporte_sha256_esperado"] = hashlib.sha256(cambiado).hexdigest()
    with pytest.raises(ValueError, match="longitud de prueba"):
        verificar_artefacto_oos(
            cambiado, **referencias, verificar_calendario=True,
        )


def test_rechaza_inicio_en_sabado_con_huellas_actualizadas():
    contenido, _ = _artefacto(inicio="2026-01-03")
    reporte = json.loads(contenido)
    registro = registrar_plan_oos(reporte["plan"])
    cambiado = json.dumps(reporte, sort_keys=True).encode()
    referencias = {
        "reporte_sha256_esperado": hashlib.sha256(cambiado).hexdigest(),
        "plan_sha256_esperado": registro["plan_sha256"],
        "dataset_sha256_esperado": "a" * 64,
    }
    with pytest.raises(ValueError, match="fuera de sesiones XNYS"):
        verificar_artefacto_oos(
            cambiado, **referencias, verificar_calendario=True,
        )


@pytest.mark.parametrize("valor", [1, "true", None, []])
def test_rechaza_flag_no_booleano(valor):
    contenido, referencias = _artefacto()
    with pytest.raises(ValueError, match="verificar_calendario debe ser booleano"):
        verificar_artefacto_oos(
            contenido, **referencias, verificar_calendario=valor,
        )


def test_cli_optin_no_expone_ruta_ni_datos(tmp_path, capsys):
    contenido, referencias = _artefacto()
    ruta = tmp_path / "privado-sintetico.json"
    ruta.write_bytes(contenido)
    assert main([
        "--reporte", str(ruta),
        "--sha256-reporte-esperado", referencias["reporte_sha256_esperado"],
        "--sha256-plan-esperado", referencias["plan_sha256_esperado"],
        "--sha256-dataset-esperado", referencias["dataset_sha256_esperado"],
        "--verificar-calendario",
    ]) == 0
    salida = capsys.readouterr().out
    assert json.loads(salida)["calendario_xnys_verificado"] is True
    assert str(ruta) not in salida
    assert "candidata-sintetica" not in salida
