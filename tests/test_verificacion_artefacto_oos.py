"""Fixtures JSON OOS sintéticos: sin precios, red, credenciales ni órdenes."""
import hashlib
import json

import pytest

from trading_ia.registro_plan_oos import registrar_plan_oos
from trading_ia.verificacion_artefacto_oos import (
    MAX_REPORTE_BYTES, main, verificar_artefacto_oos,
)


def artefacto():
    plan = {
        "schema_version": 1,
        "dataset_sha256": "a" * 64,
        "baseline_id": "V3.1",
        "candidata_id": "prueba",
        "baseline_parametros_sha256": "b" * 64,
        "candidata_parametros_sha256": "c" * 64,
        "universo": ["AAPL"],
        "inicio_prueba": "2026-01-05",
        "fin_prueba": "2026-01-30",
        "coste_bps_por_lado": 2.0,
        "ventanas": {
            "entrenamiento": 10, "validacion": 5, "prueba": 3,
            "embargo": 2, "horizonte_etiqueta": 2, "paso": 3,
        },
        "hipotesis": "Comparación sintética sin predicción.",
    }
    registro = registrar_plan_oos(plan)
    reporte = {
        "schema_version": 1,
        "plan_sha256": registro["plan_sha256"],
        "plan": registro["plan"],
        "comparacion": {
            "schema_version": 1,
            "id_baseline": "V3.1",
            "id_candidata": "prueba",
            "baseline": {
                "ventanas": 1, "operaciones": 0,
                "por_ventana": [{"inicio_prueba": "2026-01-05",
                                 "fin_prueba": "2026-01-30", "operaciones": 0,
                                 "expectativa_r": None}],
            },
            "candidata": {
                "ventanas": 1, "operaciones": 0,
                "por_ventana": [{"inicio_prueba": "2026-01-05",
                                 "fin_prueba": "2026-01-30", "operaciones": 0,
                                 "expectativa_r": None}],
            },
            "por_ventana": [{"inicio_prueba": "2026-01-05",
                             "fin_prueba": "2026-01-30",
                             "operaciones_baseline": 0, "operaciones_candidata": 0,
                             "expectativa_r_baseline": None,
                             "expectativa_r_candidata": None,
                             "diferencia_media_r_descriptiva": None}],
        },
        "advertencia": "datos enteramente sintéticos",
    }
    contenido = json.dumps(reporte, ensure_ascii=False, sort_keys=True).encode()
    hashes = {
        "reporte_sha256_esperado": hashlib.sha256(contenido).hexdigest(),
        "plan_sha256_esperado": registro["plan_sha256"],
        "dataset_sha256_esperado": "a" * 64,
    }
    return contenido, hashes


def test_verifica_cadena_y_no_devuelve_resultados_ni_precios():
    contenido, hashes = artefacto()
    antes = bytes(contenido)
    resultado = verificar_artefacto_oos(contenido, **hashes)
    assert resultado["reporte_sha256"] == hashes["reporte_sha256_esperado"]
    assert resultado["plan_sha256"] == hashes["plan_sha256_esperado"]
    assert resultado["dataset_sha256_declarado"] == "a" * 64
    assert resultado["reporte_bytes"] == len(contenido)
    assert "sintéticos" not in json.dumps(resultado)
    assert contenido == antes


def test_rechaza_modificacion_de_un_byte():
    contenido, hashes = artefacto()
    with pytest.raises(ValueError, match="Huella SHA-256 de reporte"):
        verificar_artefacto_oos(contenido + b" ", **hashes)


@pytest.mark.parametrize("campo", [
    "reporte_sha256_esperado", "plan_sha256_esperado", "dataset_sha256_esperado",
])
def test_rechaza_compromiso_externo_incorrecto(campo):
    contenido, hashes = artefacto()
    hashes[campo] = "f" * 64
    with pytest.raises(ValueError, match="Huella"):
        verificar_artefacto_oos(contenido, **hashes)


@pytest.mark.parametrize("campo", [
    "reporte_sha256_esperado", "plan_sha256_esperado", "dataset_sha256_esperado",
])
def test_rechaza_hash_no_canonico(campo):
    contenido, hashes = artefacto()
    hashes[campo] = "A" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        verificar_artefacto_oos(contenido, **hashes)


def test_rechaza_plan_interno_adulterado_aun_con_hash_reporte_actualizado():
    contenido, hashes = artefacto()
    reporte = json.loads(contenido)
    reporte["plan"]["hipotesis"] = "hipótesis diferente"
    modificado = json.dumps(reporte).encode()
    hashes["reporte_sha256_esperado"] = hashlib.sha256(modificado).hexdigest()
    with pytest.raises(ValueError, match="Huella de plan"):
        verificar_artefacto_oos(modificado, **hashes)


def test_rechaza_dataset_declarado_distinto_del_compromiso():
    contenido, hashes = artefacto()
    hashes["dataset_sha256_esperado"] = "d" * 64
    with pytest.raises(ValueError, match="dataset"):
        verificar_artefacto_oos(contenido, **hashes)


@pytest.mark.parametrize("contenido", [
    b'{"schema_version":1,"schema_version":1}',
    b'{"schema_version":1,"plan":{"universo":[],"universo":[]}}',
    b'{"schema_version":1,"comparacion":{"r":NaN}}',
    b'{"schema_version":1,"comparacion":{"r":1e400}}',
    b'\xff',
    b'{"schema_version":',
])
def test_rechaza_json_ambiguo_o_no_finito(contenido):
    _, hashes = artefacto()
    hashes["reporte_sha256_esperado"] = hashlib.sha256(contenido).hexdigest()
    with pytest.raises(ValueError, match="duplicada|finita|finito|JSON"):
        verificar_artefacto_oos(contenido, **hashes)


def test_rechaza_schema_booleano_y_comparacion_no_objeto():
    contenido, hashes = artefacto()
    for cambios in ({"schema_version": True}, {"comparacion": []}):
        reporte = json.loads(contenido)
        reporte.update(cambios)
        nuevo = json.dumps(reporte).encode()
        hashes["reporte_sha256_esperado"] = hashlib.sha256(nuevo).hexdigest()
        with pytest.raises(ValueError, match="Esquema"):
            verificar_artefacto_oos(nuevo, **hashes)


@pytest.mark.parametrize("contenido", [b"", b"x" * (MAX_REPORTE_BYTES + 1), "no bytes", True])
def test_rechaza_entrada_vacia_excesiva_o_no_bytes(contenido):
    _, hashes = artefacto()
    with pytest.raises(ValueError, match="bytes"):
        verificar_artefacto_oos(contenido, **hashes)


def test_cli_local_solo_emite_huellas_y_no_contenido(tmp_path, capsys):
    contenido, hashes = artefacto()
    ruta = tmp_path / "reporte-sintetico.json"
    ruta.write_bytes(contenido)
    args = [
        "--reporte", str(ruta),
        "--sha256-reporte-esperado", hashes["reporte_sha256_esperado"],
        "--sha256-plan-esperado", hashes["plan_sha256_esperado"],
        "--sha256-dataset-esperado", hashes["dataset_sha256_esperado"],
    ]
    assert main(args) == 0
    salida = capsys.readouterr().out
    assert json.loads(salida)["reporte_bytes"] == len(contenido)
    assert str(ruta) not in salida
    assert "sintéticos" not in salida
    assert ruta.read_bytes() == contenido


def _revalidar_mutacion(cambio, mensaje):
    contenido, hashes = artefacto()
    reporte = json.loads(contenido)
    cambio(reporte)
    alterado = json.dumps(reporte, ensure_ascii=False, sort_keys=True).encode()
    # Incluso con el hash del archivo recalculado, la estructura debe fallar.
    hashes["reporte_sha256_esperado"] = hashlib.sha256(alterado).hexdigest()
    with pytest.raises(ValueError, match=mensaje):
        verificar_artefacto_oos(alterado, **hashes)


@pytest.mark.parametrize("campo", ["id_baseline", "id_candidata"])
def test_rechaza_identidad_de_estrategia_distinta_del_plan(campo):
    _revalidar_mutacion(
        lambda reporte: reporte["comparacion"].__setitem__(campo, "otra-estrategia"),
        "Identificadores de comparación",
    )


def test_rechaza_conteos_contradictorios_entre_resumenes():
    _revalidar_mutacion(
        lambda reporte: reporte["comparacion"]["por_ventana"][0].__setitem__(
            "operaciones_baseline", 1
        ),
        "Conteos por ventana baseline",
    )


def test_rechaza_fechas_de_bloques_inconsistentes():
    _revalidar_mutacion(
        lambda reporte: reporte["comparacion"]["candidata"]["por_ventana"][0].__setitem__(
            "fin_prueba", "2026-01-29"
        ),
        "Fechas por ventana candidata",
    )


def test_rechaza_totales_inconsistentes():
    _revalidar_mutacion(
        lambda reporte: reporte["comparacion"]["baseline"].__setitem__("operaciones", 1),
        "Total de operaciones baseline",
    )


def test_rechaza_limites_de_comparacion_distintos_del_plan():
    _revalidar_mutacion(
        lambda reporte: reporte["comparacion"]["por_ventana"][0].__setitem__(
            "inicio_prueba", "2026-01-06"
        ),
        "Límites de comparación",
    )


def test_rechaza_comparacion_incompleta_aunque_tenga_hash_valido():
    _revalidar_mutacion(
        lambda reporte: reporte["comparacion"].pop("baseline"),
        "Resumen baseline ausente",
    )


def _con_medias_sinteticas():
    """Cifras inventadas y coherentes; NO prueba ejecución ni rentabilidad."""
    contenido, hashes = artefacto()
    reporte = json.loads(contenido)
    fila = reporte["comparacion"]["por_ventana"][0]
    for nombre, media in (("baseline", 0.5), ("candidata", 0.25)):
        agregado = reporte["comparacion"][nombre]
        agregado["operaciones"] = 1
        agregado["por_ventana"][0]["operaciones"] = 1
        agregado["por_ventana"][0]["expectativa_r"] = media
        fila[f"operaciones_{nombre}"] = 1
        fila[f"expectativa_r_{nombre}"] = media
    fila["diferencia_media_r_descriptiva"] = -0.25
    return reporte, hashes


def _verificar_con_nueva_huella(reporte, hashes):
    serializado = json.dumps(reporte, sort_keys=True).encode()
    referencias = {**hashes, "reporte_sha256_esperado": hashlib.sha256(serializado).hexdigest()}
    return verificar_artefacto_oos(serializado, **referencias)


def test_acepta_medias_y_diferencia_r_coherentes_sinteticas():
    reporte, hashes = _con_medias_sinteticas()
    assert _verificar_con_nueva_huella(reporte, hashes)["schema_version"] == 1


@pytest.mark.parametrize("campo,valor,mensaje", [
    ("expectativa_r_baseline", 0.6, "Expectativa R baseline"),
    ("expectativa_r_candidata", True, "Expectativa R candidata"),
    ("diferencia_media_r_descriptiva", 0.25, "Diferencia media R inconsistente"),
    ("diferencia_media_r_descriptiva", None, "Diferencia media R inconsistente"),
])
def test_rechaza_medias_o_delta_alterados_con_hash_recalculado(campo, valor, mensaje):
    reporte, hashes = _con_medias_sinteticas()
    reporte["comparacion"]["por_ventana"][0][campo] = valor
    with pytest.raises(ValueError, match=mensaje):
        _verificar_con_nueva_huella(reporte, hashes)


def test_rechaza_media_de_resumen_distinta_a_comparacion():
    reporte, hashes = _con_medias_sinteticas()
    reporte["comparacion"]["baseline"]["por_ventana"][0]["expectativa_r"] = 0.4
    with pytest.raises(ValueError, match="Expectativa R baseline"):
        _verificar_con_nueva_huella(reporte, hashes)


def test_rechaza_expectativa_no_nula_en_ventana_sin_operaciones():
    contenido, hashes = artefacto()
    reporte = json.loads(contenido)
    reporte["comparacion"]["por_ventana"][0]["expectativa_r_baseline"] = 0.0
    with pytest.raises(ValueError, match="Expectativa R baseline"):
        _verificar_con_nueva_huella(reporte, hashes)


def test_rechaza_delta_no_finito_derivado_de_medias_finitas():
    reporte, hashes = _con_medias_sinteticas()
    for nombre, valor in (("baseline", -1e308), ("candidata", 1e308)):
        reporte["comparacion"][nombre]["por_ventana"][0]["expectativa_r"] = valor
        reporte["comparacion"]["por_ventana"][0][f"expectativa_r_{nombre}"] = valor
    with pytest.raises(ValueError, match="Diferencia media R no finita"):
        _verificar_con_nueva_huella(reporte, hashes)


def test_rechaza_entero_json_enorme_en_media_sin_desbordar_excepcion():
    reporte, hashes = _con_medias_sinteticas()
    reporte["comparacion"]["baseline"]["por_ventana"][0]["expectativa_r"] = 10 ** 400
    with pytest.raises(ValueError, match="Expectativa R baseline"):
        _verificar_con_nueva_huella(reporte, hashes)
