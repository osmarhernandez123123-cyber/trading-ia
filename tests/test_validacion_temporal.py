"""Validación cronológica sintética: nunca consulta datos ni credenciales."""
from datetime import date, datetime, timedelta

import pytest

from trading_ia.validacion_temporal import crear_ventanas


def sesiones(cuantas=40):
    # Fechas sintéticas preseleccionadas; la función cuenta sesiones, no días.
    inicio = date(2026, 1, 1)
    return tuple(inicio + timedelta(days=i) for i in range(cuantas))


def test_ventanas_cronologicas_embargadas_y_pruebas_sin_solape():
    resultado = crear_ventanas(
        sesiones(), entrenamiento=10, validacion=5, prueba=5,
        embargo=2, horizonte_etiqueta=2,
    )
    assert len(resultado) == 4
    pruebas_anteriores = set()
    for ventana in resultado:
        assert len(ventana.entrenamiento) == 10
        assert len(ventana.validacion) == 5
        assert len(ventana.prueba) == 5
        assert len(ventana.embargo_validacion) == 2
        assert len(ventana.embargo_prueba) == 2
        bloques = (
            ventana.entrenamiento, ventana.embargo_validacion,
            ventana.validacion, ventana.embargo_prueba, ventana.prueba,
        )
        assert all(a[-1] < b[0] for a, b in zip(bloques, bloques[1:]))
        assert len(set().union(*map(set, bloques))) == 24
        assert not pruebas_anteriores.intersection(ventana.prueba)
        pruebas_anteriores.update(ventana.prueba)
        assert ventana.inicio_prueba == ventana.prueba[0]
        assert ventana.fin_prueba == ventana.prueba[-1]


def test_resultado_determinista_y_sin_mutar_entrada():
    entrada = list(sesiones())
    copia = entrada.copy()
    parametros = dict(entrenamiento=6, validacion=4, prueba=3, embargo=1)
    a = crear_ventanas(entrada, **parametros)
    b = crear_ventanas(entrada, **parametros)
    assert a == b
    assert entrada == copia
    assert len(a) > 1


def test_paso_mayor_deja_pruebas_no_solapadas():
    resultado = crear_ventanas(
        sesiones(), entrenamiento=8, validacion=4, prueba=3,
        embargo=1, paso=6,
    )
    assert len(resultado) > 1
    assert all(a.fin_prueba < b.inicio_prueba for a, b in zip(resultado, resultado[1:]))


@pytest.mark.parametrize("incorrecto", [
    [date(2026, 1, 2), date(2026, 1, 1)],
    [date(2026, 1, 1), date(2026, 1, 1)],
    [datetime(2026, 1, 1)],
    ["2026-01-01"],
])
def test_rechaza_fechas_ambiguas_duplicadas_o_desordenadas(incorrecto):
    with pytest.raises(ValueError, match="sesiones"):
        crear_ventanas(incorrecto, entrenamiento=2, validacion=2, prueba=2)


@pytest.mark.parametrize("nombre,valor", [
    ("entrenamiento", 0), ("validacion", -1), ("prueba", 0),
    ("embargo", 0), ("horizonte_etiqueta", 0),
    ("prueba", True), ("embargo", 1.5),
])
def test_rechaza_configuraciones_invalidas(nombre, valor):
    parametros = dict(entrenamiento=8, validacion=4, prueba=3, embargo=1)
    parametros[nombre] = valor
    with pytest.raises(ValueError, match=nombre):
        crear_ventanas(sesiones(), **parametros)


def test_embargo_no_puede_ser_menor_al_horizonte_de_etiqueta():
    with pytest.raises(ValueError, match="embargo"):
        crear_ventanas(sesiones(), entrenamiento=8, validacion=4,
                      prueba=3, embargo=1, horizonte_etiqueta=3)


@pytest.mark.parametrize("paso", [0, 1, 2, -1, 1.5, True])
def test_no_admite_pruebas_solapadas_ni_pasos_invalidos(paso):
    with pytest.raises(ValueError, match="paso"):
        crear_ventanas(sesiones(), entrenamiento=8, validacion=4,
                      prueba=3, paso=paso)


def test_historial_insuficiente_se_rechaza():
    with pytest.raises(ValueError, match="Historial insuficiente"):
        crear_ventanas(sesiones(20), entrenamiento=10,
                      validacion=5, prueba=5, embargo=2)


def test_ninguna_operacion_ni_prediccion_ocurre_en_el_generador():
    resultado = crear_ventanas(
        sesiones(30), entrenamiento=8, validacion=4, prueba=3,
        embargo=2, horizonte_etiqueta=2,
    )
    assert resultado
    assert not hasattr(resultado[0], "pnl")
    assert not hasattr(resultado[0], "senales")
