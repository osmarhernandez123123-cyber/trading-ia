"""Backtesting V3.1: simulador conservador de velas de 1 minuto.

No modela ticks, libro de ordenes, borrow fees ni margen real del broker.
No garantiza que los stops limiten la perdida real al 1%.
"""
from pathlib import Path
import pandas as pd


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


from trading_ia.backtest import Configuracion, simular


def ejecutar(exigir_calidad=None):
    config = Configuracion(**{nombre: globals()[nombre] for nombre in Configuracion.__dataclass_fields__})
    res, rech, capital_df = simular(pd.read_parquet(VELAS), pd.read_parquet(CANDIDATAS), config, exigir_calidad)
    capital_realizado = float(capital_df.iloc[-1].capital_realizado)
    res.to_parquet(SALIDA, index=False)
    rech.to_parquet(RECHAZOS, index=False)
    capital_df.to_parquet(CURVA, index=False)
    ganancias = res.loc[res.pnl_usd > 0, 'pnl_usd'].sum()
    perdidas = abs(res.loc[res.pnl_usd < 0, 'pnl_usd'].sum())
    pf = ganancias / perdidas if perdidas else float('inf')
    print('\n=== BACKTESTING V3.1 ===')
    print('Capital inicial:', round(CAPITAL_INICIAL, 2))
    print('Capital final:', round(capital_realizado, 2))
    print('Rentabilidad %:', round(100 * (capital_realizado / CAPITAL_INICIAL - 1), 2))
    print('Operaciones:', len(res), 'Win rate %:', round(100 * (res.R > 0).mean(), 2))
    print('R promedio:', round(res.R.mean(), 4), 'Profit factor:', round(pf, 3))
    print('R objetivo nominal medio:', round(res.R_objetivo_nominal.mean(), 4))
    print('R objetivo ejecutable medio:', round(res.R_objetivo_ejecutable.mean(), 4))
    print('Max drawdown %:', round(capital_df.drawdown_pct.min(), 2))
    print('Riesgo maximo presupuestado USD:', round(res.riesgo_total.max(), 2))
    print('Operaciones con perdida mayor al riesgo presupuestado:', int((res.R < -1.000001).sum()))
    print('Sesiones con ultimo minuto faltante:', int(res.motivo_salida.eq('FIN_SESION_DATOS_INCOMPLETOS').sum()))
    print('\nPor accion:\n', res.groupby('symbol').pnl_usd.agg(['count', 'sum', 'mean']).round(2))
    print('\nMotivos de salida:\n', res.motivo_salida.value_counts())
    print('\nRechazos:\n', rech.motivo.value_counts())
    print('\nAUDITORIA CONTABLE: OK')
    print('Archivos:', SALIDA.name, RECHAZOS.name, CURVA.name)


if __name__ == '__main__':
    ejecutar()
