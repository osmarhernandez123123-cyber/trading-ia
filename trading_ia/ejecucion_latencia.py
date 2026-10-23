"""Modelo alternativo explícito de cotizaciones observadas; nunca envía órdenes.

No reconstruye ticks desde OHLC. Niveles y cantidad se congelan al observar una
cotización tras el cierre de señal; el fill ocurre en otro evento posterior.
"""
from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from .backtest import Configuracion
from .calendario import anotar_sesion


def _tiempos(serie):
    if any(pd.isna(t) or pd.Timestamp(t).tzinfo is None for t in serie):
        raise ValueError('Se requieren timestamps verificables con zona horaria')
    return pd.to_datetime(serie, utc=True)


def preparar_intenciones(senales):
    """Solo información al cierre: dirección y distancia ATR original ×1.5.

    timestamp etiqueta el INICIO del minuto de señal. conocido_desde representa
    su cierre nominal; disponibilidad real del proveedor puede ser posterior.
    Ningún campo de la próxima vela se consulta, ni se exige que esta exista.
    """
    g = senales[['symbol', 'timestamp', 'SENAL', 'ATR_14']].copy()
    g['timestamp'] = _tiempos(g.timestamp)
    if g.symbol.isna().any() or g.symbol.astype(str).str.strip().eq('').any():
        raise ValueError('Símbolo inválido en señales')
    if g.SENAL.isna().any() or not g.SENAL.isin(['LONG', 'SHORT', 'NO TRADE']).all():
        raise ValueError('Categoría de señal inválida')
    if g.duplicated(['symbol', 'timestamp']).any():
        raise ValueError('Señales duplicadas')
    g = g.sort_values(['symbol', 'timestamp'])
    anterior = g.groupby('symbol').SENAL.shift(1)
    nueva = g.SENAL.isin(['LONG', 'SHORT']) & g.SENAL.ne(anterior)
    # No filtrar primero: una entrada con ATR ausente/cero se perdería en silencio.
    distancia = pd.to_numeric(g.ATR_14, errors='coerce') * 1.5
    validas = np.isfinite(distancia) & distancia.gt(0)
    if not validas[nueva].all():
        raise ValueError('Distancia ATR inválida para una nueva señal')
    g['distancia_sl'] = distancia
    g = g[nueva].copy()
    g['conocido_desde'] = g.timestamp + pd.Timedelta(minutes=1)
    return g[['symbol', 'timestamp', 'conocido_desde', 'SENAL', 'distancia_sl']].reset_index(drop=True)


@dataclass
class ResultadoLatencia:
    ordenes: pd.DataFrame
    operaciones: pd.DataFrame
    curva: pd.DataFrame
    estado_final: pd.DataFrame


def simular_latencia(cotizaciones, intenciones, *, latencia_ms, demora_datos_ms=0,
                     config=Configuracion()):
    """Cotizaciones bid/ask con timestamp de DISPONIBILIDAD, no de publicación.

    Primera cotización recibida tras conocido_desde + demora_datos_ms: observar,
    fijar niveles y cantidad. Primera cotización recibida >= envío + latencia_ms:
    ejecutar cantidad ya fijada al ask (LONG) o bid (SHORT), más slippage original.
    Una cotización extrema posterior no cancela selectivamente una orden enviada.
    Stops/objetivos se disparan con bid/ask observados, nunca con high/low futuros.
    Solo la entrada tiene latencia; salidas instantáneas son una limitación explícita.
    """
    if config.LATENCIA_VELAS != 0:
        raise ValueError('No mezclar LATENCIA_VELAS con el modelo de cotizaciones')
    if not np.isfinite([latencia_ms, demora_datos_ms]).all() or latencia_ms <= 0 or demora_datos_ms < 0:
        raise ValueError('Latencia positiva y demora de datos no negativa requeridas')
    q = cotizaciones[['symbol', 'timestamp', 'bid', 'ask']].copy()
    q['timestamp'] = _tiempos(q.timestamp)
    if q.empty or q.duplicated(['symbol', 'timestamp']).any():
        raise ValueError('Cotizaciones vacías o duplicadas')
    if q.symbol.isna().any() or q.symbol.astype(str).str.strip().eq('').any():
        raise ValueError('Símbolo inválido')
    q[['bid', 'ask']] = q[['bid', 'ask']].astype(float)
    precios = q[['bid', 'ask']].to_numpy(dtype=float)
    if not np.isfinite(precios).all() or (precios <= 0).any() or (q.bid > q.ask).any():
        raise ValueError('Bid/ask inválidos')
    if q.timestamp.dt.tz_convert(config.ZONA).dt.date.nunique() != 1:
        raise ValueError('Modelo experimental por sesión: separar fechas explícitamente')
    q = q.sort_values(['timestamp', 'symbol'])
    sesiones = anotar_sesion(q.timestamp, config.CALENDARIO)
    if not sesiones.en_horario.all():
        raise ValueError('Cotización fuera de sesión regular')
    q['corte'] = sesiones.ultima_vela.to_numpy()  # cierre programado al inicio del último minuto
    i = intenciones[['symbol', 'timestamp', 'conocido_desde', 'SENAL', 'distancia_sl']].copy()
    for campo in ['timestamp', 'conocido_desde']:
        i[campo] = _tiempos(i[campo])
    if i.symbol.isna().any() or i.symbol.astype(str).str.strip().eq('').any():
        raise ValueError('Símbolo inválido en intenciones')
    if i.duplicated(['symbol', 'timestamp']).any() or not i.SENAL.isin(['LONG', 'SHORT']).all():
        raise ValueError('Intenciones inválidas o duplicadas')
    if not (i.conocido_desde == i.timestamp + pd.Timedelta(minutes=1)).all():
        raise ValueError('Señal disponible antes de su cierre o timestamp incoherente')
    if not np.isfinite(i.distancia_sl).all() or not i.distancia_sl.gt(0).all():
        raise ValueError('Distancia inválida')
    i['disponible'] = i.conocido_desde + pd.to_timedelta(demora_datos_ms, unit='ms')
    i['fecha'] = i.timestamp.dt.tz_convert(config.ZONA).dt.date
    espera = i.sort_values(['disponible', 'symbol']).to_dict('records')
    ordenes, operaciones, curva = [], [], []
    pendientes, activas, marcas = {}, {}, {}
    efectivo = config.CAPITAL_INICIAL

    def fill(precio, signo, entrada):
        return float(precio) * (1 + (signo if entrada else -signo) * config.SLIPPAGE_BPS / 10000)

    def patrimonio():
        return efectivo + sum(p['signo'] * p['acciones'] *
            marcas[s]['bid' if p['signo'] == 1 else 'ask'] for s, p in activas.items())

    def cerrar(s, t, motivo):
        nonlocal efectivo
        p = activas.pop(s)
        precio = marcas[s]['bid' if p['signo'] == 1 else 'ask']
        salida = fill(precio, p['signo'], False)
        n = p['acciones']
        efectivo += p['signo'] * n * salida - n * config.COMISION_ACCION
        pnl = p['signo'] * n * (salida - p['entrada']) - 2 * n * config.COMISION_ACCION
        operaciones.append({**p, 'salida_timestamp': t, 'salida': salida,
                            'motivo_salida': motivo, 'pnl_usd': pnl,
                            'R_presupuestado': pnl / p['riesgo_presupuestado']})

    def comprobar_salida(s, t):
        p = activas[s]
        px = marcas[s]['bid' if p['signo'] == 1 else 'ask']
        if p['signo'] * (px - p['stop_loss']) <= 0:
            cerrar(s, t, 'STOP_COTIZACION')
        elif p['signo'] * (px - p['take_profit']) >= 0:
            cerrar(s, t, 'OBJETIVO_COTIZACION')

    # Recorre únicamente eventos observados, en orden; ningún último precio futuro.
    for t, bloque in q.groupby('timestamp', sort=True):
        for v in bloque.to_dict('records'):
            s = v['symbol']
            marcas[s] = v
        # Salidas antes de entradas, con la misma prioridad alfabética de V3.1.
        for v in bloque.to_dict('records'):
            s = v['symbol']
            if s in activas:
                if t >= v['corte']:
                    cerrar(s, t, 'CIERRE_PROGRAMADO')
                else:
                    comprobar_salida(s, t)
        for v in bloque.to_dict('records'):
            s = v['symbol']
            if s in pendientes:
                orden = pendientes[s]
                if t >= orden['corte']:
                    orden['estado'] = 'EXPIRADA_SESION'
                    del pendientes[s]
                elif t >= orden['llegada_timestamp']:
                    # Cantidad, SL y TP son inmutables desde envío. El gap se asume.
                    entrada = fill(v['ask'] if orden['signo'] == 1 else v['bid'], orden['signo'], True)
                    n = orden['acciones']
                    efectivo -= orden['signo'] * n * entrada + n * config.COMISION_ACCION
                    orden.update(estado='EJECUTADA', entrada_timestamp=t, entrada=entrada,
                                 nocional_al_fill=n * entrada,
                                 exceso_nocional_sobre_reserva=max(0., n * entrada - orden['nocional_presupuestado']))
                    activas[s] = orden.copy()
                    del pendientes[s]
                    comprobar_salida(s, t)  # bracket inmediato: limitación declarada
            nuevas = [x for x in espera if x['symbol'] == s and x['disponible'] <= t]
            for intento in nuevas:
                espera.remove(intento)
                orden = dict(intento, estado='RECHAZADA', motivo='', observacion_timestamp=t)
                ordenes.append(orden)
                if t >= v['corte'] or intento['fecha'] != t.tz_convert(config.ZONA).date():
                    orden['motivo'] = 'FUERA_VENTANA'
                    continue
                if s in pendientes or s in activas:
                    orden['motivo'] = 'POSICION_U_ORDEN_EXISTENTE'
                    continue
                if len(pendientes) + len(activas) >= config.MAX_POSICIONES:
                    orden['motivo'] = 'MAX_POSICIONES'
                    continue
                signo = 1 if intento['SENAL'] == 'LONG' else -1
                referencia = (v['bid'] + v['ask']) / 2
                sl = referencia - signo * intento['distancia_sl']
                tp = referencia + signo * 2 * intento['distancia_sl']
                if sl <= 0 or tp <= 0:
                    orden['motivo'] = 'NIVELES_NO_POSITIVOS'
                    continue
                esperado = fill(v['ask'] if signo == 1 else v['bid'], signo, True)
                riesgo = signo * (esperado - fill(sl, signo, False)) + 2 * config.COMISION_ACCION
                equity = patrimonio()
                reservadas = list(activas.values()) + list(pendientes.values())
                usado = sum(p['riesgo_presupuestado'] for p in reservadas)
                nocional = sum(p['nocional_presupuestado'] for p in reservadas)
                presupuesto = min(max(0., equity * config.RIESGO_OPERACION), max(0., equity * config.RIESGO_TOTAL - usado))
                n = min(math.floor(presupuesto / riesgo), math.floor(max(0., equity - nocional) / (esperado + config.COMISION_ACCION)))
                if n < 1:
                    orden['motivo'] = 'CAPITAL_O_RIESGO_INSUFICIENTE'
                    continue
                orden.update(estado='ENVIADA', signo=signo, referencia=referencia,
                    stop_loss=sl, take_profit=tp, acciones=n, corte=v['corte'],
                    riesgo_presupuestado=n * riesgo, nocional_presupuestado=n * esperado,
                    envio_timestamp=t, llegada_timestamp=t + pd.to_timedelta(latencia_ms, unit='ms'))
                pendientes[s] = orden
        curva.append({'timestamp': t, 'patrimonio': patrimonio(), 'efectivo': efectivo,
                      'posiciones': len(activas), 'ordenes_pendientes': len(pendientes)})
    # Un dataset truncado no autoriza un fill/cierre retroactivo en su último tick.
    estado = ([dict(symbol=s, estado='POSICION_ABIERTA_FIN_DATOS') for s in activas]
              + [dict(symbol=s, estado='ORDEN_PENDIENTE_FIN_DATOS') for s in pendientes]
              + [dict(symbol=x['symbol'], estado='SIN_COTIZACION_TRAS_SENAL') for x in espera])
    if not activas:
        pnl_total = sum(p['pnl_usd'] for p in operaciones)
        if not math.isclose(efectivo, config.CAPITAL_INICIAL + pnl_total, abs_tol=.02):
            raise AssertionError('Desbalance contable de la ejecución alternativa')
    return ResultadoLatencia(pd.DataFrame(ordenes), pd.DataFrame(operaciones),
                             pd.DataFrame(curva), pd.DataFrame(estado, columns=['symbol', 'estado']))
