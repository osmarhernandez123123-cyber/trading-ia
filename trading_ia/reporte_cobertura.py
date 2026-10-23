"""Diagnóstico local de cobertura de barras intradía, sin acceso a red.

El reporte contabiliza ausencias respecto al calendario, pero NO infiere
si faltan operaciones elegibles, si el proveedor omitió datos o si hubo una
interrupción del feed. No fabrica ni interpola velas.
"""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import string

import pandas as pd

from .calendario import ZONA_NY, clasificar_cobertura, horario_sesiones, minutos_esperados


def _fecha(valor: date | str, nombre: str) -> date:
    if type(valor) is date:
        return valor
    if not isinstance(valor, str):
        raise ValueError(f"{nombre} debe ser una fecha ISO YYYY-MM-DD")
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ValueError(f"{nombre} debe ser una fecha ISO YYYY-MM-DD") from exc


def _timestamps(datos: pd.Series) -> pd.DatetimeIndex:
    # pd.to_datetime(..., utc=True) acepta fechas naive como si fueran UTC.
    # Evitamos esa conversión implícita porque altera la sesión y el DST.
    for valor in datos:
        try:
            fecha = pd.Timestamp(valor)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Timestamp ilegible o ausente") from exc
        if pd.isna(fecha):
            raise ValueError("Timestamp ilegible o ausente")
        if fecha.tzinfo is None:
            raise ValueError("Timestamp sin zona horaria explícita")
    return pd.DatetimeIndex(pd.to_datetime(datos, utc=True))


def crear_reporte_cobertura(
    datos: pd.DataFrame,
    *,
    fuente: str,
    calendario: str = "XNYS",
    inicio: date | str | None = None,
    fin: date | str | None = None,
) -> dict:
    """Cuenta minutos observados/esperados por símbolo y sesión de mercado.

    inicio y fin permiten incluir sesiones completamente ausentes en
    los extremos. Sin ellos el intervalo va de la primera a la última fecha
    observada, por lo que no se pueden inferir sesiones fuera de ese rango.
    Todos los timestamps deben llevar zona horaria. Las barras extendidas se
    cuentan por separado, nunca como cobertura de la sesión regular.
    """
    if not isinstance(fuente, str) or not fuente.strip():
        raise ValueError("fuente es obligatoria (identificador del proveedor)")
    if not {"symbol", "timestamp"}.issubset(datos.columns):
        raise ValueError("Se requieren columnas symbol y timestamp")
    if datos.empty:
        raise ValueError("Dataset vacío: no es posible inferir símbolos")
    if datos["symbol"].isna().any() or not datos["symbol"].map(
        lambda x: isinstance(x, str) and bool(x.strip())
    ).all():
        raise ValueError("Símbolo ausente o inválido")

    df = datos[["symbol", "timestamp"]].copy()
    df["timestamp"] = _timestamps(df["timestamp"])
    if df.duplicated(["symbol", "timestamp"]).any():
        raise ValueError("Barras duplicadas por símbolo y timestamp")

    fechas = df["timestamp"].dt.tz_convert(ZONA_NY).dt.date
    inicio = _fecha(inicio, "inicio") if inicio is not None else min(fechas)
    fin = _fecha(fin, "fin") if fin is not None else max(fechas)
    if inicio > fin:
        raise ValueError("inicio no puede ser posterior a fin")
    if ((fechas < inicio) | (fechas > fin)).any():
        raise ValueError("Hay observaciones fuera del rango de sesiones solicitado")

    horario = horario_sesiones(inicio, fin, calendario)
    if horario.empty:
        raise ValueError("El intervalo no contiene sesiones bursátiles")
    simbolos = sorted(df["symbol"].unique().tolist())
    filas = []
    resumen_simbolos = []
    esperado_global = set()
    for fecha in horario.index:
        esperado_global.update(minutos_esperados(fecha, calendario))

    for simbolo in simbolos:
        timestamps = df.loc[df["symbol"].eq(simbolo), "timestamp"]
        cobertura = clasificar_cobertura(timestamps, inicio, fin, calendario)
        totales = {"minutos_esperados": 0, "minutos_presentes": 0, "minutos_faltantes": 0}
        completas = 0
        sin_datos = 0
        for registro in cobertura.to_dict("records"):
            esperados = int(registro["minutos_esperados"])
            presentes = int(registro["minutos_presentes"])
            faltantes = int(registro["minutos_faltantes"])
            filas.append({
                "symbol": simbolo,
                "fecha": str(registro["fecha"]),
                "estado": registro["estado"],
                "cierre_anticipado": bool(registro["cierre_anticipado"]),
                "minutos_esperados": esperados,
                "minutos_presentes": presentes,
                "minutos_faltantes": faltantes,
                "fraccion_cobertura": round(presentes / esperados, 6),
            })
            for clave, valor in (("minutos_esperados", esperados),
                                 ("minutos_presentes", presentes),
                                 ("minutos_faltantes", faltantes)):
                totales[clave] += valor
            completas += faltantes == 0
            sin_datos += presentes == 0
        resumen_simbolos.append({
            "symbol": simbolo,
            **totales,
            "fraccion_cobertura": round(
                totales["minutos_presentes"] / totales["minutos_esperados"], 6
            ),
            "sesiones_completas": completas,
            "sesiones_sin_datos": sin_datos,
        })

    total_esperados = sum(r["minutos_esperados"] for r in resumen_simbolos)
    total_presentes = sum(r["minutos_presentes"] for r in resumen_simbolos)
    return {
        "schema_version": 1,
        "fuente": fuente.strip(),
        "calendario": calendario.upper(),
        "zona_sesion": ZONA_NY,
        "inicio": str(inicio),
        "fin": str(fin),
        "filas_entrada": len(df),
        "filas_fuera_regular": int((~df["timestamp"].isin(esperado_global)).sum()),
        "resumen": {
            "simbolos": len(simbolos),
            "sesiones_por_simbolo": len(horario),
            "minutos_esperados": total_esperados,
            "minutos_presentes": total_presentes,
            "minutos_faltantes": total_esperados - total_presentes,
            "fraccion_cobertura": round(total_presentes / total_esperados, 6),
        },
        "por_simbolo": resumen_simbolos,
        "sesiones": filas,
        "advertencia": (
            "Las ausencias no prueban un fallo del proveedor: pueden reflejar "
            "minutos sin transacciones, cortes del feed o datos truncados. "
            "No se rellenaron barras; revisar procedencia y evidencia externa."
        ),
    }


def _sha256_archivo(ruta: Path) -> str:
    """Huella de los bytes exactos del archivo, sin cargarlo en memoria."""
    digest = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", type=Path, help="CSV o Parquet local con symbol y timestamp")
    parser.add_argument("--fuente", required=True, help="Proveedor/feed, p. ej. IEX")
    parser.add_argument("--calendario", default="XNYS", choices=("XNYS", "XNAS"))
    parser.add_argument("--inicio", help="Primera fecha de sesión YYYY-MM-DD")
    parser.add_argument("--fin", help="Última fecha de sesión YYYY-MM-DD")
    parser.add_argument("--salida", type=Path, help="Ruta local de reporte JSON; por defecto stdout")
    parser.add_argument(
        "--sha256-esperado",
        help="SHA-256 esperado (64 caracteres hexadecimales) para verificar el archivo",
    )
    args = parser.parse_args(argv)
    if args.salida is not None and args.salida.resolve() == args.archivo.resolve():
        parser.error("--salida no puede sobrescribir el dataset de entrada")
    if args.archivo.suffix.lower() not in (".csv", ".parquet"):
        parser.error("Solo se admiten archivos CSV o Parquet")
    if args.sha256_esperado is not None and (
        len(args.sha256_esperado) != 64
        or any(c not in string.hexdigits for c in args.sha256_esperado)
    ):
        parser.error("--sha256-esperado debe tener 64 caracteres hexadecimales")
    huella = _sha256_archivo(args.archivo)
    if args.sha256_esperado is not None and huella != args.sha256_esperado.lower():
        raise ValueError("SHA-256 del dataset no coincide con el esperado")
    if args.archivo.suffix.lower() == ".parquet":
        datos = pd.read_parquet(args.archivo, columns=["symbol", "timestamp"])
    elif args.archivo.suffix.lower() == ".csv":
        datos = pd.read_csv(args.archivo, usecols=["symbol", "timestamp"])
    else:
        parser.error("Solo se admiten archivos CSV o Parquet")
    reporte = crear_reporte_cobertura(
        datos, fuente=args.fuente, calendario=args.calendario,
        inicio=args.inicio, fin=args.fin,
    )
    # Solo la huella criptográfica, nunca la ruta local ni datos del archivo.
    reporte["archivo_sha256"] = huella
    reporte["archivo_bytes"] = args.archivo.stat().st_size
    salida = json.dumps(reporte, ensure_ascii=False, indent=2) + "\n"
    if args.salida is None:
        print(salida, end="")
    else:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(salida, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
