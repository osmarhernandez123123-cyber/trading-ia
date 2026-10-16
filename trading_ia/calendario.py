"""Calendario de mercado para velas estadounidenses de un minuto.

Las velas del proyecto están etiquetadas por el inicio del minuto. Por eso una
sesión normal termina en 15:59 NY y una sesión con cierre a las 13:00 termina en
12:59 NY.
"""

from __future__ import annotations

from functools import lru_cache

import exchange_calendars as xcals
import pandas as pd

ZONA_NY = "America/New_York"
CALENDARIOS = {"NYSE": "XNYS", "NASDAQ": "XNAS", "XNYS": "XNYS", "XNAS": "XNAS"}


@lru_cache(maxsize=4)
def obtener_calendario(nombre: str = "XNYS"):
    """Devuelve un calendario conocido o falla sin elegir uno implícitamente."""
    try:
        codigo = CALENDARIOS[nombre.upper()]
    except KeyError as exc:
        raise ValueError(f"Calendario no soportado: {nombre}") from exc
    return xcals.get_calendar(codigo)


def horario_sesiones(inicio, fin, nombre: str = "XNYS") -> pd.DataFrame:
    """Horario UTC inclusivo por fecha de sesión, con indicador de cierre temprano."""
    cal = obtener_calendario(nombre)
    inicio = pd.Timestamp(inicio).date()
    fin = pd.Timestamp(fin).date()
    horario = cal.schedule.loc[str(inicio):str(fin), ["open", "close"]].copy()
    horario.index = pd.Index([x.date() for x in horario.index], name="fecha")
    duracion = horario["close"] - horario["open"]
    horario["minutos_esperados"] = (duracion / pd.Timedelta(minutes=1)).astype(int)
    horario["cierre_anticipado"] = horario["minutos_esperados"] < 390
    horario["ultima_vela"] = horario["close"] - pd.Timedelta(minutes=1)
    return horario


def minutos_esperados(fecha, nombre: str = "XNYS") -> pd.DatetimeIndex:
    """Índice UTC de inicios de vela esperados para una fecha de sesión."""
    horario = horario_sesiones(fecha, fecha, nombre)
    if horario.empty:
        return pd.DatetimeIndex([], tz="UTC")
    fila = horario.iloc[0]
    return pd.date_range(
        fila["open"], fila["close"], freq="1min", inclusive="left", tz="UTC"
    )


def anotar_sesion(timestamps, nombre: str = "XNYS") -> pd.DataFrame:
    """Clasifica timestamps UTC como minuto regular, fuera de sesión o no hábil."""
    serie = pd.Series(pd.to_datetime(timestamps, utc=True))
    fechas = serie.dt.tz_convert(ZONA_NY).dt.date
    if serie.empty:
        return pd.DataFrame(index=serie.index, columns=[
            "fecha", "minuto_ny", "es_sesion", "en_horario",
            "cierre_anticipado", "ultima_vela"
        ])
    horario = horario_sesiones(fechas.min(), fechas.max(), nombre)
    mapa = horario.to_dict("index")
    filas = []
    locales = serie.dt.tz_convert(ZONA_NY)
    for timestamp, fecha, local in zip(serie, fechas, locales):
        sesion = mapa.get(fecha)
        es_sesion = sesion is not None
        en_horario = bool(
            es_sesion and sesion["open"] <= timestamp < sesion["close"]
        )
        filas.append({
            "fecha": fecha,
            "minuto_ny": local.hour * 60 + local.minute,
            "es_sesion": es_sesion,
            "en_horario": en_horario,
            "cierre_anticipado": bool(sesion["cierre_anticipado"]) if es_sesion else False,
            "ultima_vela": sesion["ultima_vela"] if es_sesion else pd.NaT,
        })
    return pd.DataFrame(filas, index=serie.index)


def clasificar_cobertura(
    timestamps,
    inicio=None,
    fin=None,
    nombre: str = "XNYS",
) -> pd.DataFrame:
    """Resume cobertura por sesión y distingue cierre temprano de datos truncados."""
    observados = pd.DatetimeIndex(pd.to_datetime(timestamps, utc=True)).drop_duplicates()
    if len(observados):
        fechas = pd.Series(observados).dt.tz_convert(ZONA_NY).dt.date
        inicio = inicio or fechas.min()
        fin = fin or fechas.max()
    elif inicio is None or fin is None:
        raise ValueError("Se requieren inicio y fin cuando no hay timestamps")

    horario = horario_sesiones(inicio, fin, nombre)
    registros = []
    conjunto = set(observados)
    for fecha, sesion in horario.iterrows():
        esperados = minutos_esperados(fecha, nombre)
        presentes = sum(t in conjunto for t in esperados)
        faltantes = len(esperados) - presentes
        estado = (
            "sin_datos" if presentes == 0
            else "completa_cierre_anticipado"
            if faltantes == 0 and sesion["cierre_anticipado"]
            else "completa" if faltantes == 0
            else "incompleta"
        )
        registros.append({
            "fecha": fecha,
            "estado": estado,
            "cierre_anticipado": bool(sesion["cierre_anticipado"]),
            "minutos_esperados": len(esperados),
            "minutos_presentes": presentes,
            "minutos_faltantes": faltantes,
            "apertura": sesion["open"],
            "cierre": sesion["close"],
            "ultima_vela_esperada": sesion["ultima_vela"],
        })
    return pd.DataFrame(registros)
