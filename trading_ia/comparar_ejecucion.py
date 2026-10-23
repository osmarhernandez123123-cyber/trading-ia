"""Comparación exclusivamente sintética de V3.1 y ejecución con latencia.

Uso: python -m trading_ia.comparar_ejecucion --salida work/comparacion.json
No consulta red, no lee datos de mercado ni optimiza parámetros.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
from importlib.metadata import version

import pandas as pd

from .backtest import Configuracion, simular
from .calendario import minutos_esperados
from .ejecucion_latencia import preparar_intenciones, simular_latencia
from .transformaciones import preparar


def escenario(movimiento, spread=0.):
    """Eventos artificiales: tres cotizaciones por minuto, sin inferencia de OHLC real.

    En la apertura 09:31 midpoint=100. Desde +1s cambia movimiento y permanece
    hasta 09:32; desde 09:32 midpoint=101.5. Una única señal LONG ya fijada.
    """
    minutos = minutos_esperados('2026-01-05')
    filas = []
    for j, minuto in enumerate(minutos):
        for segundos in [0, 1, 59]:
            precio = 100. if j == 0 or (j == 1 and segundos == 0) else 100. + movimiento if j == 1 else 101.5
            filas.append(dict(symbol='TEST', timestamp=minuto + pd.Timedelta(seconds=segundos),
                              bid=precio - spread / 2, ask=precio + spread / 2))
    cotizaciones = pd.DataFrame(filas)
    cotizaciones['mid'] = (cotizaciones.bid + cotizaciones.ask) / 2
    grupos = cotizaciones.groupby(cotizaciones.timestamp.dt.floor('min'))
    velas = grupos.mid.agg(open='first', high='max', low='min', close='last').reset_index()
    velas['symbol'] = 'TEST'
    velas['volume'] = 1000
    velas['SENAL'] = 'NO TRADE'
    velas.loc[0, 'SENAL'] = 'LONG'
    velas['ATR_14'] = 1 / 1.5
    return velas, cotizaciones.drop(columns='mid')


def _hash(tabla):
    return hashlib.sha256(tabla.to_json(orient='split', date_format='iso', double_precision=15).encode()).hexdigest()


def comparar():
    config = Configuracion()
    resultado = {'tipo': 'EXCLUSIVAMENTE_SINTETICO', 'no_demuestra_rentabilidad': True,
                 'python': platform.python_version(),
                 'versiones': {p: version(p) for p in ['pandas', 'numpy', 'exchange-calendars']},
                 'configuracion_v31_sin_cambios': asdict(config),
                 'latencia_entrada_ms': 500, 'demora_datos_ms': 0,
                 'escenarios': []}
    for movimiento, spread in [(0., 0.), (.5, 0.), (-.5, 0.), (.5, .1)]:
        velas, cotizaciones = escenario(movimiento, spread)
        operaciones, rechazos, curva = simular(velas, preparar(velas))
        intenciones = preparar_intenciones(velas)
        alternativo = simular_latencia(cotizaciones, intenciones, latencia_ms=500, config=config)
        if not alternativo.estado_final.empty:
            raise AssertionError('Comparación sintética incompleta')
        delta = float(alternativo.operaciones.pnl_usd.sum() - operaciones.pnl_usd.sum())
        resultado['escenarios'].append({
            'movimiento_durante_latencia': movimiento, 'spread_absoluto': spread,
            'hash_velas': _hash(velas), 'hash_cotizaciones': _hash(cotizaciones),
            'v31': {'operaciones': len(operaciones), 'pnl_usd': float(operaciones.pnl_usd.sum()),
                    'capital_final': float(curva.iloc[-1].patrimonio),
                    'entrada': float(operaciones.iloc[0].entrada), 'acciones': int(operaciones.iloc[0].acciones),
                    'hash_operaciones': _hash(operaciones)},
            'latencia': {'operaciones': len(alternativo.operaciones),
                         'pnl_usd': float(alternativo.operaciones.pnl_usd.sum()),
                         'capital_final': float(alternativo.curva.iloc[-1].patrimonio),
                         'entrada': float(alternativo.operaciones.iloc[0].entrada),
                         'acciones': int(alternativo.operaciones.iloc[0].acciones),
                         'hash_operaciones': _hash(alternativo.operaciones),
                         'ordenes': json.loads(alternativo.ordenes.to_json(orient='records', date_format='iso'))},
            'delta_pnl_latencia_menos_v31': delta})
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, required=True)
    args = parser.parse_args()
    resultado = comparar()
    repetido = comparar()
    if resultado != repetido:
        raise AssertionError('Comparaciones no deterministas')
    resultado['dos_ejecuciones_identicas'] = True
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    # No sobreescribir investigaciones existentes.
    with args.salida.open('x') as archivo:
        json.dump(resultado, archivo, indent=2, ensure_ascii=False, allow_nan=False)
        archivo.write('\n')
    print(f'Comparación sintética guardada en {args.salida}')


if __name__ == '__main__':
    main()
