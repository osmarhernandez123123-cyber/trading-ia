import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent
VELAS = BASE / 'datos_senales.parquet'
CANDIDATAS = BASE / 'entradas_candidatas.parquet'
SALIDA = BASE / 'resultados_backtesting_v2.parquet'
RECHAZOS = BASE / 'rechazos_backtesting_v2.parquet'

# Hipotesis de ejecucion: modificar segun broker y liquidez reales.
SLIPPAGE_BPS = 2.0  # 0.02% adverso en cada ejecucion
COMISION_POR_ACCION = 0.0  # USD por accion y por lado
RIESGO_MAXIMO_TOTAL_R = 3.0  # maximo de posiciones simultaneas, 1R cada una
ZONA = 'America/New_York'

velas = pd.read_parquet(VELAS).reset_index(drop=True)
candidatas = pd.read_parquet(CANDIDATAS).reset_index(drop=True)
for nombre, df in [('velas', velas), ('candidatas', candidatas)]:
    requeridas = {'symbol', 'timestamp'}
    if nombre == 'velas':
        requeridas |= {'open', 'high', 'low', 'close'}
    else:
        requeridas |= {'entrada_timestamp', 'SENAL', 'stop_loss', 'take_profit'}
    faltan = requeridas - set(df.columns)
    if faltan:
        raise ValueError(f'{nombre}: columnas faltantes {faltan}')
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    if df.duplicated(['symbol', 'timestamp']).any():
        raise ValueError(f'{nombre}: symbol/timestamp duplicados')
candidatas['entrada_timestamp'] = pd.to_datetime(candidatas['entrada_timestamp'], utc=True)
velas = velas.sort_values(['timestamp', 'symbol']).copy()
candidatas = candidatas.sort_values(['entrada_timestamp', 'symbol']).copy()

# Solo velas regulares; no suponemos ejecuciones fuera de mercado.
local = velas['timestamp'].dt.tz_convert(ZONA)
minuto = local.dt.hour * 60 + local.dt.minute
velas = velas[(minuto >= 570) & (minuto < 960)].copy()
velas['fecha'] = velas['timestamp'].dt.tz_convert(ZONA).dt.date

# Cada candidata debe ser generada exactamente una vela antes de la entrada.
candidatas = candidatas[(candidatas['entrada_timestamp'] - candidatas['timestamp']).dt.total_seconds() == 60].copy()
if candidatas.duplicated(['symbol', 'entrada_timestamp']).any():
    raise ValueError('Hay multiples candidatas para el mismo simbolo y minuto')
indice = {(r.symbol, r.entrada_timestamp): r for r in candidatas.itertuples(index=False)}

operaciones, rechazos = [], []
activas = {}
ultimo_por_simbolo = {}

def precio_con_deslizamiento(precio, direccion, entrada):
    # Compra: peor precio mas alto. Venta: peor precio mas bajo.
    signo = (1 if direccion == 'LONG' else -1) * (1 if entrada else -1)
    return float(precio) * (1 + signo * SLIPPAGE_BPS / 10000)

def cerrar(pos, precio_base, tiempo, motivo):
    salida = precio_con_deslizamiento(precio_base, pos['direccion'], False)
    sentido = 1 if pos['direccion'] == 'LONG' else -1
    bruto = sentido * (salida - pos['entrada'])
    costo = 2 * COMISION_POR_ACCION
    pos.update(salida=salida, salida_timestamp=tiempo, motivo_salida=motivo,
               R=(bruto - costo) / pos['riesgo_unitario'])
    operaciones.append(pos)

for vela in velas.itertuples(index=False):
    s, t, fecha = vela.symbol, vela.timestamp, vela.fecha
    bloqueada = False
    pos = activas.get(s)
    if pos is not None:
        if fecha != pos['fecha']:
            cerrar(pos, pos['ultimo_close'], pos['ultimo_timestamp'], 'FIN_SESION')
            del activas[s]
            bloqueada = True
        else:
            sl, tp = pos['stop_loss'], pos['take_profit']
            long = pos['direccion'] == 'LONG'
            # Si abre mas alla del stop/objetivo, ejecutar a la apertura.
            gap_sl = (vela.open <= sl) if long else (vela.open >= sl)
            gap_tp = (vela.open >= tp) if long else (vela.open <= tp)
            toca_sl = (vela.low <= sl) if long else (vela.high >= sl)
            toca_tp = (vela.high >= tp) if long else (vela.low <= tp)
            if gap_sl:
                cerrar(pos, vela.open, t, 'GAP_STOP')
            elif gap_tp:
                cerrar(pos, vela.open, t, 'GAP_TP')
            elif toca_sl:
                cerrar(pos, sl, t, 'STOP_LOSS')  # ambos: SL primero
            elif toca_tp:
                cerrar(pos, tp, t, 'TAKE_PROFIT')
            else:
                pos['ultimo_close'] = float(vela.close)
                pos['ultimo_timestamp'] = t
            if operaciones and operaciones[-1] is pos:
                del activas[s]
                bloqueada = True

    candidato = indice.get((s, t))
    if candidato is not None:
        motivo = None
        direccion = candidato.SENAL
        if bloqueada or s in activas:
            motivo = 'POSICION_EXISTENTE_O_SALIDA_MISMA_VELA'
        elif len(activas) >= int(RIESGO_MAXIMO_TOTAL_R):
            motivo = 'LIMITE_EXPOSICION'
        elif direccion not in ('LONG', 'SHORT'):
            motivo = 'DIRECCION_INVALIDA'
        elif not np.isfinite([vela.open, vela.high, vela.low, vela.close,
                              candidato.stop_loss, candidato.take_profit]).all():
            motivo = 'PRECIOS_NO_VALIDOS'
        elif float(vela.open) <= 0:
            motivo = 'PRECIO_NO_POSITIVO'
        else:
            entrada = precio_con_deslizamiento(vela.open, direccion, True)
            sl = float(candidato.stop_loss)
            tp = float(candidato.take_profit)
            if not ((sl < entrada < tp) if direccion == 'LONG' else (tp < entrada < sl)):
                motivo = 'NIVELES_INVALIDOS_TRAS_SLIPPAGE'
            else:
                riesgo = abs(entrada - sl)
                if riesgo <= 2 * COMISION_POR_ACCION:
                    motivo = 'RIESGO_INSUFICIENTE'
                else:
                    activas[s] = dict(symbol=s, fecha=fecha, direccion=direccion,
                        senal_timestamp=candidato.timestamp, entrada_timestamp=t,
                        entrada=entrada, stop_loss=sl, take_profit=tp,
                        riesgo_unitario=riesgo, ultimo_close=float(vela.close), ultimo_timestamp=t)
                    # La vela de entrada tambien puede tocar SL/TP.
                    # Sin datos tick, se resuelve conservadoramente.
                    pos_nueva = activas[s]
                    toca_sl = (vela.low <= sl) if direccion == 'LONG' else (vela.high >= sl)
                    toca_tp = (vela.high >= tp) if direccion == 'LONG' else (vela.low <= tp)
                    if toca_sl:
                        cerrar(pos_nueva, sl, t, 'STOP_LOSS_ENTRADA')
                        del activas[s]
                    elif toca_tp:
                        cerrar(pos_nueva, tp, t, 'TAKE_PROFIT_ENTRADA')
                        del activas[s]
        if motivo:
            rechazos.append(dict(symbol=s, entrada_timestamp=t, motivo=motivo))
    ultimo_por_simbolo[s] = (fecha, t, float(vela.close))

for s, pos in list(activas.items()):
    cerrar(pos, pos['ultimo_close'], pos['ultimo_timestamp'], 'FIN_DATOS')

res = pd.DataFrame(operaciones)
if res.empty:
    raise RuntimeError('No se generaron operaciones; revisar candidatos y datos')
res = res.sort_values(['salida_timestamp', 'symbol']).reset_index(drop=True)
res.to_parquet(SALIDA, index=False)
pd.DataFrame(rechazos, columns=['symbol', 'entrada_timestamp', 'motivo']).to_parquet(RECHAZOS, index=False)
positivas = res.loc[res.R > 0, 'R']
negativas = res.loc[res.R < 0, 'R']
profit_factor = positivas.sum() / abs(negativas.sum()) if len(negativas) and negativas.sum() != 0 else float('inf')
curva = res.R.cumsum()
drawdown = (curva - curva.cummax().clip(lower=0)).min()
print('=== BACKTESTING V2 ===')
print('Operaciones:', len(res), 'Rechazadas:', len(rechazos))
print('Win rate:', round(100 * (res.R > 0).mean(), 2), '%')
print('R promedio:', round(res.R.mean(), 4), 'R acumulado:', round(res.R.sum(), 2))
print('Profit factor:', round(profit_factor, 3), 'Drawdown aproximado:', round(drawdown, 2), 'R')
print('\nPor simbolo:\n', res.groupby('symbol').R.agg(['count', 'mean', 'sum']))
print('\nMotivos de salida:\n', res.motivo_salida.value_counts())
print('\nRechazos:\n', pd.DataFrame(rechazos).motivo.value_counts() if rechazos else 'Ninguno')
print('Archivos:', SALIDA.name, RECHAZOS.name)
