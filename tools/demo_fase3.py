"""Genera una sesión SINTÉTICA solo para verificar la infraestructura offline."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('salida', type=Path)
    args = p.parse_args()
    if args.salida.exists():
        p.error('El destino ya existe')
    tiempos = pd.date_range('2026-01-05 14:30', periods=390, freq='min', tz='UTC')
    precio = 100 + np.sin(np.arange(390) / 6) * .5 + np.arange(390) * .002
    df = pd.DataFrame(dict(symbol='TEST', timestamp=tiempos, open=precio,
                           high=precio+.2, low=precio-.2, close=precio+.01, volume=1000))
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.salida, index=False)


if __name__ == '__main__':
    main()
