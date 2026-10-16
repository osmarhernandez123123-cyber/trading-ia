"""Backtesting V3.1: simulador conservador de velas de 1 minuto.

No modela ticks, libro de ordenes, borrow fees ni margen real del broker.
No garantiza que los stops limiten la perdida real al 1%.
"""
from pathlib import Path
import numpy as np
import pandas as pd

from trading_ia.calendario import anotar_sesion
from trading_ia.calidad_datos import validar_ohlcv

BASE = Path(__file__).resolve().parent
VELAS = BASE / 'datos_senales.parquet'
CANDIDATAS = BASE / 'entradas_candidatas.parquet'
SALIDA = BASE / 'resultados_backtesting_v3_1.parquet'
RECHAZOS = BASE / 'rechazos_backtesting_v3_1.parquet'
CURVA = BASE / 'capital_backtesting_v3_1.parquet'

CAPITAL_INICIAL = 100_000.0
RIESGO_OPERACION = 0.01
RIESGO_TOTAL = 0.03
MAX_POSICIONES = 3
SLIPPAGE_BPS = 2.0
COMISION_ACCION = 0.0
ZONA = 'America/New_York'
CALENDARIO = 'XNYS'
EXIGIR_CALIDAD_ESTRICTA = True
TOL = 1e-6


def ejecutar(exigir_calidad=None):
    from trading_ia.backtest import Configuracion, simular
    config = Configuracion(**{n: globals()[n] for n in Configuracion.__dataclass_fields__})
    res, rech, curva = simular(pd.read_parquet(VELAS), pd.read_parquet(CANDIDATAS),
                              config, EXIGIR_CALIDAD_ESTRICTA if exigir_calidad is None else exigir_calidad)
    res.to_parquet(SALIDA, index=False)
    rech.to_parquet(RECHAZOS, index=False)
    curva.to_parquet(CURVA, index=False)
    print('BACKTESTING V3.1 — AUDITORIA CONTABLE: OK; operaciones:', len(res))
    return res, rech, curva

if __name__ == '__main__':
    ejecutar()
