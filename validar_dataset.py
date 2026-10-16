"""CLI local para validar un Parquet y generar reporte/manifiesto JSON."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from trading_ia.calidad_datos import (
    POLITICA_ESTRICTA,
    POLITICA_EXTENDIDO_ALPACA,
    POLITICA_IEX_CONSERVADORA,
    POLITICA_SOLO_REGULAR,
    crear_manifiesto,
    escribir_json,
    validar_ohlcv,
)


def argumentos():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parquet", type=Path)
    parser.add_argument("--reporte", type=Path, required=True)
    parser.add_argument("--manifiesto", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--fuente", required=True)
    parser.add_argument("--licencia", required=True)
    parser.add_argument("--calendario", choices=["XNYS", "XNAS"], default="XNYS")
    parser.add_argument(
        "--politica-huecos",
        choices=["estricta", "iex-conservadora"],
        default="estricta",
        help="Clasifica ausencias; ninguna opción crea o rellena velas",
    )
    parser.add_argument(
        "--politica-sesion",
        choices=["solo-regular", "extendido-permitido"],
        default="solo-regular",
        help="Ventana temporal admitida en el artefacto original",
    )
    return parser.parse_args()


def main() -> int:
    args = argumentos()
    datos = pd.read_parquet(args.parquet)
    if isinstance(datos.index, pd.MultiIndex) or datos.index.name is not None:
        datos = datos.reset_index()
    politica = (
        POLITICA_ESTRICTA
        if args.politica_huecos == "estricta"
        else POLITICA_IEX_CONSERVADORA
    )
    politica_sesion = (
        POLITICA_SOLO_REGULAR
        if args.politica_sesion == "solo-regular"
        else POLITICA_EXTENDIDO_ALPACA
    )
    reporte = validar_ohlcv(
        datos, args.calendario, politica_huecos=politica,
        politica_sesion=politica_sesion,
    )
    manifiesto = crear_manifiesto(
        args.parquet, datos, args.dataset_id, args.version, args.fuente,
        args.licencia, args.calendario,
    )
    escribir_json(reporte.a_dict(), args.reporte)
    escribir_json(manifiesto, args.manifiesto)
    print(f"Reporte: {args.reporte}")
    print(f"Manifiesto: {args.manifiesto}")
    print(f"Dataset válido: {reporte.valido}")
    print(f"Apto para indicadores continuos: {reporte.apto_indicadores}")
    return 0 if reporte.valido and reporte.apto_indicadores else 2


if __name__ == "__main__":
    raise SystemExit(main())
