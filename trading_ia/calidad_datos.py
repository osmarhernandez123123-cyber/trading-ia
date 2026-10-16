"""Validación reproducible de datasets OHLCV intradía."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .calendario import ZONA_NY, anotar_sesion, clasificar_cobertura

COLUMNAS_REQUERIDAS = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}


@dataclass(frozen=True)
class Incidencia:
    codigo: str
    gravedad: str
    cantidad: int
    descripcion: str
    symbol: str | None = None


@dataclass
class ReporteCalidad:
    filas: int
    simbolos: list[str]
    inicio_utc: str | None
    fin_utc: str | None
    incidencias: list[Incidencia]
    sesiones: list[dict[str, Any]]

    @property
    def valido(self) -> bool:
        return not any(x.gravedad == "ERROR" for x in self.incidencias)

    def a_dict(self) -> dict[str, Any]:
        return {
            "valido": self.valido,
            "filas": self.filas,
            "simbolos": self.simbolos,
            "inicio_utc": self.inicio_utc,
            "fin_utc": self.fin_utc,
            "resumen_incidencias": {
                gravedad: sum(x.cantidad for x in self.incidencias if x.gravedad == gravedad)
                for gravedad in ("ERROR", "ADVERTENCIA")
            },
            "incidencias": [asdict(x) for x in self.incidencias],
            "sesiones": self.sesiones,
        }


def _iso(valor) -> str | None:
    return None if pd.isna(valor) else pd.Timestamp(valor).isoformat()


def validar_ohlcv(
    datos: pd.DataFrame,
    calendario: str = "XNYS",
    comprobar_cobertura: bool = True,
    umbral_salto: float = 0.50,
) -> ReporteCalidad:
    """Valida estructura, orden, OHLCV, calendario, huecos y saltos anómalos."""
    faltantes = COLUMNAS_REQUERIDAS - set(datos.columns)
    if faltantes:
        raise ValueError(f"Columnas faltantes: {sorted(faltantes)}")
    df = datos.copy()
    incidencias: list[Incidencia] = []
    timestamp_original = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    nat = int(timestamp_original.isna().sum())
    if nat:
        incidencias.append(Incidencia("TIMESTAMP_INVALIDO", "ERROR", nat, "Timestamp ausente o ilegible"))
    df["timestamp"] = timestamp_original

    duplicados = int(df.duplicated(["symbol", "timestamp"], keep=False).sum())
    if duplicados:
        incidencias.append(Incidencia("DUPLICADO", "ERROR", duplicados, "Filas con symbol/timestamp duplicado"))
    for simbolo, grupo in df.groupby("symbol", sort=False, dropna=False):
        validos = grupo["timestamp"].dropna()
        desordenados = int((validos.diff().dropna() <= pd.Timedelta(0)).sum())
        if desordenados:
            incidencias.append(Incidencia(
                "DESORDENADO", "ERROR", desordenados,
                "Timestamps no estrictamente crecientes en el orden de entrada", str(simbolo),
            ))

    numericas = ["open", "high", "low", "close", "volume"]
    for columna in numericas:
        df[columna] = pd.to_numeric(df[columna], errors="coerce")
    no_finitos = ~np.isfinite(df[numericas].to_numpy(dtype=float))
    cantidad_no_finitos = int(no_finitos.sum())
    if cantidad_no_finitos:
        incidencias.append(Incidencia("VALOR_NO_FINITO", "ERROR", cantidad_no_finitos, "OHLCV contiene NaN o infinito"))

    precios = df[["open", "high", "low", "close"]]
    no_positivos = int((precios <= 0).any(axis=1).sum())
    if no_positivos:
        incidencias.append(Incidencia("PRECIO_NO_POSITIVO", "ERROR", no_positivos, "Fila con precio cero o negativo"))
    ohlc_inconsistente = (
        (df["high"] < df[["open", "close", "low"]].max(axis=1))
        | (df["low"] > df[["open", "close", "high"]].min(axis=1))
    )
    if ohlc_inconsistente.any():
        incidencias.append(Incidencia("OHLC_INCONSISTENTE", "ERROR", int(ohlc_inconsistente.sum()), "High/low no contiene open, close y rango"))
    volumen_negativo = int((df["volume"] < 0).sum())
    if volumen_negativo:
        incidencias.append(Incidencia("VOLUMEN_NEGATIVO", "ERROR", volumen_negativo, "Volumen negativo"))
    volumen_cero = int((df["volume"] == 0).sum())
    if volumen_cero:
        incidencias.append(Incidencia("VOLUMEN_CERO", "ADVERTENCIA", volumen_cero, "Velas sin volumen; comprobar feed"))

    con_timestamp = df[df["timestamp"].notna()].copy()
    if not con_timestamp.empty:
        anotacion = anotar_sesion(con_timestamp["timestamp"], calendario)
        fuera = int((~anotacion["en_horario"]).sum())
        if fuera:
            incidencias.append(Incidencia("FUERA_DE_SESION", "ERROR", fuera, "Timestamp en festivo o fuera del horario regular"))

    sesiones: list[dict[str, Any]] = []
    if comprobar_cobertura and not con_timestamp.empty:
        fechas = con_timestamp["timestamp"].dt.tz_convert(ZONA_NY).dt.date
        inicio, fin = fechas.min(), fechas.max()
        for simbolo, grupo in con_timestamp.groupby("symbol", sort=True):
            cobertura = clasificar_cobertura(grupo["timestamp"], inicio, fin, calendario)
            for registro in cobertura.to_dict("records"):
                registro["symbol"] = str(simbolo)
                for clave in ("apertura", "cierre", "ultima_vela_esperada"):
                    registro[clave] = _iso(registro[clave])
                registro["fecha"] = str(registro["fecha"])
                sesiones.append(registro)
            incompletas = cobertura[cobertura["estado"].isin(["incompleta", "sin_datos"])]
            if not incompletas.empty:
                incidencias.append(Incidencia(
                    "HUECOS_DE_SESION", "ERROR", int(incompletas["minutos_faltantes"].sum()),
                    "Minutos esperados ausentes según calendario", str(simbolo),
                ))

    for simbolo, grupo in con_timestamp.sort_values(["symbol", "timestamp"]).groupby("symbol"):
        continuidad = grupo["timestamp"].diff().eq(pd.Timedelta(minutes=1))
        saltos = grupo["close"].pct_change(fill_method=None).abs().gt(umbral_salto) & continuidad
        if saltos.any():
            incidencias.append(Incidencia(
                "SALTO_PRECIO", "ADVERTENCIA", int(saltos.sum()),
                f"Cambio absoluto de cierre superior a {umbral_salto:.0%} en un minuto", str(simbolo),
            ))

    simbolos = sorted(con_timestamp["symbol"].dropna().astype(str).unique().tolist())
    return ReporteCalidad(
        filas=len(df), simbolos=simbolos,
        inicio_utc=_iso(con_timestamp["timestamp"].min()),
        fin_utc=_iso(con_timestamp["timestamp"].max()),
        incidencias=incidencias, sesiones=sesiones,
    )


def sha256_archivo(ruta: str | Path, tamano_bloque: int = 1024 * 1024) -> str:
    """Calcula SHA-256 sobre los bytes exactos del artefacto."""
    digest = hashlib.sha256()
    with Path(ruta).open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(tamano_bloque), b""):
            digest.update(bloque)
    return digest.hexdigest()


def crear_manifiesto(
    ruta: str | Path,
    datos: pd.DataFrame,
    dataset_id: str,
    version: str,
    fuente: str,
    licencia: str,
    calendario: str = "XNYS",
    frecuencia: str = "1min",
) -> dict[str, Any]:
    """Crea metadatos sin copiar datos ni secretos al repositorio."""
    if not all([dataset_id.strip(), version.strip(), fuente.strip(), licencia.strip()]):
        raise ValueError("dataset_id, version, fuente y licencia son obligatorios")
    ruta = Path(ruta)
    timestamps = pd.to_datetime(datos.get("timestamp"), utc=True, errors="coerce")
    return {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "dataset_version": version,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact": {
            "filename": ruta.name,
            "bytes": ruta.stat().st_size,
            "sha256": sha256_archivo(ruta),
        },
        "provenance": {"source": fuente, "license": licencia},
        "market": {"calendar": calendario, "timezone": "UTC", "frequency": frecuencia},
        "data": {
            "rows": len(datos),
            "columns": list(datos.columns),
            "dtypes": {col: str(tipo) for col, tipo in datos.dtypes.items()},
            "symbols": sorted(datos["symbol"].dropna().astype(str).unique().tolist()),
            "start_utc": _iso(timestamps.min()),
            "end_utc": _iso(timestamps.max()),
        },
    }


def escribir_json(contenido: dict[str, Any], destino: str | Path) -> None:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".tmp")
    temporal.write_text(json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporal.replace(destino)
