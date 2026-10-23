"""Ventanas walk-forward deterministas por sesión, sin datos futuros.

Solo construye índices cronológicos. No ajusta modelos ni consulta mercados.
El embargo se mide en SESIONES, no en días calendario, y debe cubrir al menos
el horizonte máximo de las etiquetas futuras para impedir solapamientos.
El bloque de prueba de cada ventana se reserva exclusivamente para evaluación.
"""
from dataclasses import dataclass
from datetime import date
from typing import Sequence


@dataclass(frozen=True)
class VentanaTemporal:
    """Conjuntos disjuntos y ordenados de fechas bursátiles."""

    entrenamiento: tuple[date, ...]
    embargo_validacion: tuple[date, ...]
    validacion: tuple[date, ...]
    embargo_prueba: tuple[date, ...]
    prueba: tuple[date, ...]

    @property
    def inicio_prueba(self) -> date:
        return self.prueba[0]

    @property
    def fin_prueba(self) -> date:
        return self.prueba[-1]


def crear_ventanas(
    sesiones: Sequence[date],
    *,
    entrenamiento: int,
    validacion: int,
    prueba: int,
    embargo: int = 1,
    horizonte_etiqueta: int = 1,
    paso: int | None = None,
) -> tuple[VentanaTemporal, ...]:
    """Construye ventanas móviles sin mezclas temporales ni pruebas solapadas.

    sesiones: fechas de sesión NY, ya deduplicadas y ordenadas, sin datetimes.
    entrenamiento/validacion/prueba: número de sesiones por bloque.
    embargo: sesiones excluidas ANTES de cada validación y prueba.
    horizonte_etiqueta: número máximo de sesiones futuras usadas por una
        etiqueta. El embargo debe ser >= dicho horizonte.
    paso: avance de la ventana, por defecto el largo del bloque de prueba;
        debe ser >= prueba para que las pruebas entre ventanas no se solapen.

    No calcular indicadores, escalar variables o escoger hiperparámetros
    sobre el bloque de prueba. Esta función no evita por sí sola otros leaks
    como revisiones de noticias, universe selection o datos no point-in-time.
    """
    parametros = {
        "entrenamiento": entrenamiento,
        "validacion": validacion,
        "prueba": prueba,
        "embargo": embargo,
        "horizonte_etiqueta": horizonte_etiqueta,
    }
    for nombre, valor in parametros.items():
        if type(valor) is not int or valor < 1:
            raise ValueError(f"{nombre} debe ser un entero positivo")
    if embargo < horizonte_etiqueta:
        raise ValueError("El embargo debe cubrir el horizonte de las etiquetas")
    if paso is None:
        paso = prueba
    if type(paso) is not int or paso < prueba:
        raise ValueError("paso debe ser un entero >= prueba, sin solapamiento")

    fechas = tuple(sesiones)
    if any(type(fecha) is not date for fecha in fechas):
        raise ValueError("sesiones debe contener fechas sin horas, no timestamps")
    if any(a >= b for a, b in zip(fechas, fechas[1:])):
        raise ValueError("sesiones debe estar estrictamente ordenada y sin duplicados")

    tamano = entrenamiento + validacion + prueba + 2 * embargo
    if len(fechas) < tamano:
        raise ValueError("Historial insuficiente para las ventanas y embargos")

    ventanas = []
    for inicio in range(0, len(fechas) - tamano + 1, paso):
        a = inicio
        b = a + entrenamiento
        c = b + embargo
        d = c + validacion
        e = d + embargo
        f = e + prueba
        ventanas.append(VentanaTemporal(
            entrenamiento=fechas[a:b],
            embargo_validacion=fechas[b:c],
            validacion=fechas[c:d],
            embargo_prueba=fechas[d:e],
            prueba=fechas[e:f],
        ))
    return tuple(ventanas)
