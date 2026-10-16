"""Motor V3.1 sin acceso a almacenamiento ni red."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .calendario import anotar_sesion
from .calidad_datos import validar_ohlcv

@dataclass(frozen=True)
class Configuracion:
    CAPITAL_INICIAL: float = 100000.0
    RIESGO_OPERACION: float = 0.01
    RIESGO_TOTAL: float = 0.03
    MAX_POSICIONES: int = 3
    SLIPPAGE_BPS: float = 2.0
    COMISION_ACCION: float = 0.0
    ZONA: str = 'America/New_York'
    CALENDARIO: str = 'XNYS'
    TOL: float = 1e-06

def simular(velas, candidatas, config=Configuracion(), exigir_calidad=True):
    velas = velas.copy().reset_index(drop=True)
    candidatas = candidatas.copy().reset_index(drop=True)
    CAPITAL_INICIAL = config.CAPITAL_INICIAL
    RIESGO_OPERACION = config.RIESGO_OPERACION
    RIESGO_TOTAL = config.RIESGO_TOTAL
    MAX_POSICIONES = config.MAX_POSICIONES
    SLIPPAGE_BPS = config.SLIPPAGE_BPS
    COMISION_ACCION = config.COMISION_ACCION
    ZONA = config.ZONA
    CALENDARIO = config.CALENDARIO
    TOL = config.TOL
    for nombre, df, requeridas in [
        ('velas', velas, {'symbol', 'timestamp', 'open', 'high', 'low', 'close'}),
        ('candidatas', candidatas, {'symbol', 'timestamp', 'entrada_timestamp', 'SENAL', 'stop_loss', 'take_profit'}),
    ]:
        faltan = requeridas - set(df.columns)
        if faltan:
            raise ValueError(f'{nombre}: columnas faltantes: {faltan}')
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        if df.duplicated(['symbol', 'timestamp']).any():
            raise ValueError(f'{nombre}: timestamps duplicados')
    if exigir_calidad:
        reporte = validar_ohlcv(velas, CALENDARIO, comprobar_cobertura=True)
        if not reporte.valido:
            codigos = sorted({x.codigo for x in reporte.incidencias if x.gravedad == 'ERROR'})
            raise ValueError(
                'Dataset no apto para backtesting estricto: '
                + ', '.join(codigos)
                + '. Ejecutar validar_dataset.py para el detalle.'
            )
    candidatas['entrada_timestamp'] = pd.to_datetime(candidatas['entrada_timestamp'], utc=True)
    velas = velas.sort_values(['timestamp', 'symbol']).copy()
    sesiones = anotar_sesion(velas['timestamp'], CALENDARIO)
    velas['en_horario_regular'] = sesiones['en_horario'].to_numpy()
    velas['cierre_anticipado'] = sesiones['cierre_anticipado'].to_numpy()
    velas['ultima_vela_esperada'] = sesiones['ultima_vela'].to_numpy()
    velas = velas[velas['en_horario_regular']].copy()
    if velas.empty:
        raise ValueError('No hay velas en horario regular')
    velas['fecha'] = velas['timestamp'].dt.tz_convert(ZONA).dt.date
    for col in ['open', 'high', 'low', 'close']:
        velas[col] = pd.to_numeric(velas[col], errors='coerce')
    precios = velas[['open', 'high', 'low', 'close']]
    if not np.isfinite(precios.to_numpy(dtype=float)).all() or (precios <= 0).any().any():
        raise ValueError('OHLC contiene valores invalidos')
    if (velas.high < velas[['open', 'close', 'low']].max(axis=1)).any() or (velas.low > velas[['open', 'close', 'high']].min(axis=1)).any():
        raise ValueError('OHLC inconsistente')
    dif = (candidatas.entrada_timestamp - candidatas.timestamp).dt.total_seconds()
    if not dif.eq(60).all():
        raise ValueError('Candidatas: entrada debe seguir a señal exactamente 60 segundos')
    claves = set(zip(velas.symbol, velas.timestamp))
    if any((c.symbol, c.timestamp) not in claves or (c.symbol, c.entrada_timestamp) not in claves
           for c in candidatas.itertuples(index=False)):
        raise ValueError('Candidatas sin vela de señal o entrada regular')
    candidatas = candidatas.copy()
    if candidatas.duplicated(['symbol', 'entrada_timestamp']).any():
        raise ValueError('Candidatas duplicadas para una misma entrada')
    indice = {(r.symbol, r.entrada_timestamp): r for r in candidatas.itertuples(index=False)}

    # La ultima barra observada puede ser anterior a las 15:59: se informa.
    finales = velas.groupby(['symbol', 'fecha']).tail(1).copy()
    incompletas = finales[finales.timestamp != finales.ultima_vela_esperada]
    if not incompletas.empty:
        print(f'ADVERTENCIA: {len(incompletas)} sesiones no llegan al cierre oficial; se cierran al ultimo dato disponible.')
    ultima = set(zip(finales.symbol, finales.timestamp))

    efectivo = CAPITAL_INICIAL
    capital_realizado = CAPITAL_INICIAL
    activas, operaciones, rechazos, curva = {}, [], [], []
    ultimo_precio = {}
    ultima_fecha = {}

    def ejec(precio, direccion, es_entrada):
        signo = 1 if direccion == 'LONG' else -1
        if not es_entrada:
            signo = -signo
        return float(precio) * (1 + signo * SLIPPAGE_BPS / 10000)

    def equity(marcas):
        total = efectivo
        for s, p in activas.items():
            px = marcas.get(s, ultimo_precio.get(s, p['entrada']))
            total += (1 if p['direccion'] == 'LONG' else -1) * p['acciones'] * px
        return float(total)

    def riesgo_abierto():
        return sum(p['riesgo_total'] for p in activas.values())

    def cerrar(s, precio, t, motivo):
        nonlocal efectivo, capital_realizado
        p = activas.pop(s)
        signo = 1 if p['direccion'] == 'LONG' else -1
        salida = ejec(precio, p['direccion'], False)
        cantidad = p['acciones']
        efectivo += signo * cantidad * salida - cantidad * COMISION_ACCION
        pnl = signo * (salida - p['entrada']) * cantidad - 2 * COMISION_ACCION * cantidad
        capital_realizado += pnl
        p.update(salida=salida, salida_timestamp=t, motivo_salida=motivo,
                 pnl_usd=pnl, R=pnl / p['riesgo_total'], capital_cierre=capital_realizado)
        operaciones.append(p)

    def rechazar(s, t, motivo):
        rechazos.append(dict(symbol=s, entrada_timestamp=t, motivo=motivo))

    for t, bloque in velas.groupby('timestamp', sort=True):
        bloque = bloque.sort_values('symbol')
        filas = list(bloque.itertuples(index=False))
        apertura = {v.symbol: float(v.open) for v in filas}
        marcas_apertura = {**ultimo_precio, **apertura}
        bloqueadas = set()

        # Cerrar cualquier posicion cuya sesion anterior termino sin barra final.
        for s, p in list(activas.items()):
            if s in apertura:
                fecha_actual = next(v.fecha for v in filas if v.symbol == s)
                if fecha_actual != p['fecha']:
                    cerrar(s, p['ultimo_close'], p['ultimo_timestamp'], 'FIN_SESION_DATOS_INCOMPLETOS')
                    bloqueadas.add(s)

        # 1. Salidas por gap en apertura, antes de evaluar nuevas entradas.
        for v in filas:
            s = v.symbol
            if s not in activas:
                continue
            p = activas[s]
            largo = p['direccion'] == 'LONG'
            if (v.open <= p['stop_loss']) if largo else (v.open >= p['stop_loss']):
                cerrar(s, v.open, t, 'GAP_STOP')
                bloqueadas.add(s)
            elif (v.open >= p['take_profit']) if largo else (v.open <= p['take_profit']):
                cerrar(s, v.open, t, 'GAP_TP')
                bloqueadas.add(s)

        # 2. Entradas a la apertura: no usar high/low/close del minuto para decidir.
        for v in filas:
            s = v.symbol
            c = indice.get((s, t))
            if c is None:
                continue
            motivo = None
            if s in activas or s in bloqueadas:
                motivo = 'POSICION_EXISTENTE_O_SALIDA_EN_APERTURA'
            elif (s, t) in ultima or t >= v.ultima_vela_esperada:
                motivo = 'ULTIMA_VELA_DISPONIBLE'
            elif len(activas) >= MAX_POSICIONES:
                motivo = 'MAX_POSICIONES'
            elif c.SENAL not in ('LONG', 'SHORT'):
                motivo = 'DIRECCION_INVALIDA'
            elif not np.isfinite([c.stop_loss, c.take_profit]).all():
                motivo = 'NIVELES_INVALIDOS'
            if motivo:
                rechazar(s, t, motivo)
                continue
            direccion = c.SENAL
            signo = 1 if direccion == 'LONG' else -1
            entrada = ejec(v.open, direccion, True)
            sl, tp = float(c.stop_loss), float(c.take_profit)
            if not ((sl < entrada < tp) if signo == 1 else (tp < entrada < sl)):
                rechazar(s, t, 'NIVELES_INVALIDOS_TRAS_SLIPPAGE')
                continue
            stop_ejec = ejec(sl, direccion, False)
            riesgo_unitario = signo * (entrada - stop_ejec) + 2 * COMISION_ACCION
            if not np.isfinite(riesgo_unitario) or riesgo_unitario <= 0:
                rechazar(s, t, 'RIESGO_INVALIDO')
                continue
            patrimonio_entrada = equity(marcas_apertura)
            presupuesto = min(max(0., patrimonio_entrada * RIESGO_OPERACION),
                              max(0., patrimonio_entrada * RIESGO_TOTAL - riesgo_abierto()))
            por_riesgo = int(np.floor(presupuesto / riesgo_unitario))
            # Restriccion conservadora sin apalancamiento; no equivale a margen de Alpaca.
            nocional_reservado = sum(p['nocional'] for p in activas.values())
            capacidad = max(0., patrimonio_entrada - nocional_reservado)
            por_capital = int(np.floor(capacidad / (entrada + COMISION_ACCION)))
            acciones = min(por_riesgo, por_capital)
            if acciones < 1:
                rechazar(s, t, 'CAPITAL_O_RIESGO_INSUFICIENTE')
                continue
            nocional = acciones * entrada
            riesgo_total = acciones * riesgo_unitario
            salida_objetivo = ejec(tp, direccion, False)
            beneficio_objetivo_unitario = (
                signo * (salida_objetivo - entrada)
                - 2 * COMISION_ACCION
            )
            r_objetivo_ejecutable = beneficio_objetivo_unitario / riesgo_unitario

            # El 2R configurado en preparar_entradas.py es nominal: sus niveles
            # se calculan sobre la apertura sin deslizamiento. Esta métrica deja
            # visible cuánto R queda realmente alcanzable con los fills modelados.
            entrada_nominal = float(getattr(c, 'entrada_precio', v.open))
            riesgo_nominal = signo * (entrada_nominal - sl)
            r_objetivo_nominal = (
                signo * (tp - entrada_nominal) / riesgo_nominal
                if np.isfinite(riesgo_nominal) and riesgo_nominal > 0
                else np.nan
            )
            efectivo -= signo * nocional + acciones * COMISION_ACCION
            activas[s] = dict(symbol=s, fecha=v.fecha, direccion=direccion,
                              senal_timestamp=c.timestamp, entrada_timestamp=t,
                              entrada=entrada, stop_loss=sl, take_profit=tp,
                              acciones=acciones, nocional=nocional,
                              riesgo_unitario=riesgo_unitario, riesgo_total=riesgo_total,
                              R_objetivo_nominal=r_objetivo_nominal,
                              R_objetivo_ejecutable=r_objetivo_ejecutable,
                              patrimonio_entrada=patrimonio_entrada,
                              ultimo_close=float(v.open), ultimo_timestamp=t)
            if riesgo_total > patrimonio_entrada * RIESGO_OPERACION + TOL:
                raise AssertionError('Exceso de riesgo presupuestado')
            if riesgo_abierto() > patrimonio_entrada * RIESGO_TOTAL + TOL:
                raise AssertionError('Exceso de riesgo simultaneo')

        # 3. Movimiento intrabar. Si SL y TP son tocados, se supone SL primero.
        for v in filas:
            s = v.symbol
            if s not in activas:
                continue
            p = activas[s]
            largo = p['direccion'] == 'LONG'
            toca_sl = v.low <= p['stop_loss'] if largo else v.high >= p['stop_loss']
            toca_tp = v.high >= p['take_profit'] if largo else v.low <= p['take_profit']
            en_entrada = p['entrada_timestamp'] == t
            if toca_sl:
                cerrar(s, p['stop_loss'], t, 'STOP_LOSS_ENTRADA' if en_entrada else 'STOP_LOSS')
            elif toca_tp:
                cerrar(s, p['take_profit'], t, 'TAKE_PROFIT_ENTRADA' if en_entrada else 'TAKE_PROFIT')
            else:
                p['ultimo_close'] = float(v.close)
                p['ultimo_timestamp'] = t

        # 4. Cierre forzado al final de cada sesion observada.
        for v in filas:
            if (v.symbol, t) in ultima and v.symbol in activas:
                motivo = (
                    'FIN_SESION'
                    if t == v.ultima_vela_esperada
                    else 'FIN_SESION_DATOS_INCOMPLETOS'
                )
                cerrar(v.symbol, v.close, t, motivo)

        ultimo_precio.update({v.symbol: float(v.close) for v in filas})
        ultima_fecha.update({v.symbol: v.fecha for v in filas})
        patrimonio = equity(ultimo_precio)
        # Identidad contable: patrimonio = capital realizado + PnL no realizado.
        no_realizado = sum((1 if p['direccion'] == 'LONG' else -1) * p['acciones'] *
                           (ultimo_precio.get(s, p['entrada']) - p['entrada']) -
                           p['acciones'] * COMISION_ACCION
                           for s, p in activas.items())
        if abs(patrimonio - (capital_realizado + no_realizado)) > 0.02:
            raise AssertionError(f'Desbalance contable en {t}: {patrimonio - capital_realizado - no_realizado}')
        curva.append(dict(timestamp=t, capital_realizado=capital_realizado,
                          patrimonio=patrimonio, posiciones_abiertas=len(activas),
                          riesgo_abierto=riesgo_abierto()))

    for s in list(activas):
        p = activas[s]
        cerrar(s, p['ultimo_close'], p['ultimo_timestamp'], 'FIN_DATOS')

    res = pd.DataFrame(operaciones)
    if res.empty:
        res = pd.DataFrame(columns=['salida_timestamp', 'symbol', 'pnl_usd'])
    res = res.sort_values(['salida_timestamp', 'symbol']).reset_index(drop=True)
    rech = pd.DataFrame(rechazos, columns=['symbol', 'entrada_timestamp', 'motivo'])
    capital_df = pd.DataFrame(curva).sort_values('timestamp')
    capital_df['maximo'] = capital_df.patrimonio.cummax().clip(lower=CAPITAL_INICIAL)
    capital_df['drawdown_pct'] = (capital_df.patrimonio / capital_df.maximo - 1) * 100
    if abs(capital_realizado - (CAPITAL_INICIAL + res.pnl_usd.sum())) > 0.02:
        raise AssertionError('PnL realizado no concuerda con el capital final')
    if abs(efectivo - capital_realizado) > 0.02:
        raise AssertionError('Efectivo final no concuerda con el capital final')
    return res, rech, capital_df
