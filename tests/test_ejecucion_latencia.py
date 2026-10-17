"""Cronología de ejecución con eventos sintéticos explícitos, sin datos reales."""
from dataclasses import asdict, replace
import hashlib
import json

import pandas as pd
import pytest

from trading_ia.backtest import Configuracion, simular
from trading_ia.ejecucion_latencia import preparar_intenciones, simular_latencia
from trading_ia.transformaciones import preparar


def t(hora):
    return pd.Timestamp(f'2026-01-05 {hora}', tz='America/New_York').tz_convert('UTC')


def senales():
    return pd.DataFrame([{'symbol': 'TEST', 'timestamp': t('09:30:00'),
                          'SENAL': 'LONG', 'ATR_14': 1 / 1.5}])


def quotes(precios=(100, 101, 102, 101), horas=('09:31:00', '09:31:01', '09:32:00', '15:59:00'), spread=0):
    return pd.DataFrame([{'symbol': 'TEST', 'timestamp': t(h), 'bid': p - spread / 2,
                          'ask': p + spread / 2} for h, p in zip(horas, precios)])


def run(q=None, signals=None, **kwargs):
    return simular_latencia(quotes() if q is None else q,
                            preparar_intenciones(senales() if signals is None else signals),
                            latencia_ms=500, **kwargs)


def test_intencion_al_cierre_no_depende_de_siguiente_vela():
    prefijo = senales()
    futuro = pd.concat([prefijo, prefijo.assign(timestamp=t('09:31:00'), SENAL='NO TRADE')])
    futuro['open'] = [100, 900]
    futuro['high'] = [101, 1000]
    futuro['low'] = [99, 1]
    pd.testing.assert_frame_equal(preparar_intenciones(prefijo), preparar_intenciones(futuro))
    assert preparar_intenciones(prefijo).conocido_desde.iloc[0] == t('09:31:00')


def test_niveles_cantidad_fijos_antes_del_fill():
    a = run()
    b = run(quotes(precios=(100, 103, 104, 105)))
    x, y = a.ordenes.iloc[0], b.ordenes.iloc[0]
    for campo in ['referencia', 'stop_loss', 'take_profit', 'acciones', 'riesgo_presupuestado', 'envio_timestamp']:
        assert x[campo] == y[campo]
    assert x.entrada != y.entrada
    assert x.entrada_timestamp > x.envio_timestamp
    assert x.entrada_timestamp >= x.llegada_timestamp
    assert x.stop_loss == 99 and x.take_profit == 102


def test_se_reproduce_la_dependencia_de_v31_al_open_futuro():
    a = senales().assign(open=100)
    a = pd.concat([a, a.assign(timestamp=t('09:31:00'), SENAL='NO TRADE')], ignore_index=True)
    b = a.copy()
    b.loc[1, 'open'] = 110
    assert preparar(a).entrada_precio.iloc[0] == 100
    assert preparar(b).entrada_precio.iloc[0] == 110
    assert preparar(b).stop_loss.iloc[0] - preparar(a).stop_loss.iloc[0] == 10
    pd.testing.assert_frame_equal(preparar_intenciones(a), preparar_intenciones(b))


def test_prefijo_de_cotizaciones_inmutable_hasta_envio():
    q = quotes()
    prefijo = run(q.iloc[:1])
    completo = run(q)
    for campo in ['acciones', 'stop_loss', 'take_profit', 'envio_timestamp', 'llegada_timestamp']:
        assert prefijo.ordenes.iloc[0][campo] == completo.ordenes.iloc[0][campo]
    assert prefijo.operaciones.empty
    assert prefijo.estado_final.estado.tolist() == ['ORDEN_PENDIENTE_FIN_DATOS']


def test_no_usa_ohlc_aunque_se_entreguen_columnas_futuras():
    a = run()
    q = quotes().assign(high=100000, low=.001, close=1)
    b = run(q)
    pd.testing.assert_frame_equal(a.ordenes, b.ordenes)
    pd.testing.assert_frame_equal(a.operaciones, b.operaciones)


def test_no_fill_antes_de_llegada_ni_precio_retroactivo():
    q = quotes(precios=(50, 100, 500, 101, 100),
               horas=('09:30:59', '09:31:00', '09:31:00.100', '09:31:01', '15:59:00'))
    a = run(q)
    assert a.ordenes.iloc[0].entrada_timestamp == t('09:31:01')
    assert a.ordenes.iloc[0].entrada == pytest.approx(101 * 1.0002)
    assert a.ordenes.iloc[0].referencia == 100


def test_gap_adverso_no_se_rechaza_tras_envio():
    a = run(quotes(precios=(100, 95, 96, 97)))
    assert a.ordenes.iloc[0].estado == 'EJECUTADA'
    assert a.operaciones.iloc[0].motivo_salida == 'STOP_COTIZACION'
    assert a.operaciones.iloc[0].entrada == pytest.approx(95 * 1.0002)
    assert a.operaciones.iloc[0].salida == pytest.approx(95 * .9998)


def test_spread_y_direccion_short():
    s = senales().assign(SENAL='SHORT')
    a = run(quotes(precios=(100, 100, 98, 98), spread=.2), signals=s)
    op = a.operaciones.iloc[0]
    assert op.entrada == pytest.approx(99.9 * .9998)
    assert op.salida == pytest.approx(98.1 * 1.0002)


def test_demora_del_feed_retrasa_observacion():
    a = run(demora_datos_ms=1500)
    assert a.ordenes.iloc[0].observacion_timestamp == t('09:32:00')
    assert a.ordenes.iloc[0].referencia == 102
    assert a.ordenes.iloc[0].estado == 'EXPIRADA_SESION'


def test_sin_tick_posterior_no_se_inventa_fill_o_cierre():
    a = run(quotes().iloc[:1])
    assert a.operaciones.empty
    assert a.estado_final.estado.tolist() == ['ORDEN_PENDIENTE_FIN_DATOS']
    b = run(quotes(precios=(100, 100), horas=('09:31:00', '09:31:01')))
    assert b.operaciones.empty
    assert b.estado_final.estado.tolist() == ['POSICION_ABIERTA_FIN_DATOS']


def test_ultima_ventana_se_conoce_por_calendario_no_por_ultimo_tick():
    a = run(quotes(precios=(100, 100, 100), horas=('09:31:00', '09:31:01', '15:59:00')))
    assert a.operaciones.iloc[0].motivo_salida == 'CIERRE_PROGRAMADO'
    assert a.estado_final.empty


@pytest.mark.parametrize('latencia', [0, -1, float('nan')])
def test_latencia_cero_o_invalida_rechazada(latencia):
    with pytest.raises(ValueError, match='Latencia'):
        simular_latencia(quotes(), preparar_intenciones(senales()), latencia_ms=latencia)


def test_intencion_no_puede_adelantar_cierre():
    i = preparar_intenciones(senales())
    i['conocido_desde'] -= pd.Timedelta(milliseconds=1)
    with pytest.raises(ValueError, match='cierre'):
        simular_latencia(quotes(), i, latencia_ms=1)


def test_cotizacion_naive_o_duplicada_rechazada():
    q = quotes()
    q['timestamp'] = q.timestamp.dt.tz_localize(None)
    with pytest.raises(ValueError, match='zona'):
        run(q)
    with pytest.raises(ValueError, match='duplicadas'):
        run(pd.concat([quotes(), quotes().iloc[:1]]))


def test_pendientes_reservan_capital_y_son_deterministas():
    q = pd.concat([quotes().assign(symbol=s) for s in ['A', 'B', 'C', 'D']])
    s = pd.concat([senales().assign(symbol=s) for s in ['A', 'B', 'C', 'D']])
    config = replace(Configuracion(), CAPITAL_INICIAL=200)
    a = run(q, signals=s, config=config)
    b = run(q.sample(frac=1, random_state=3), signals=s.iloc[::-1], config=config)
    pd.testing.assert_frame_equal(a.ordenes, b.ordenes)
    assert a.ordenes.acciones.dropna().sum() <= 1
    assert 'CAPITAL_O_RIESGO_INSUFICIENTE' in a.ordenes.motivo.tolist()


def test_referencia_v31_sin_cambios():
    # Parámetros y transformaciones de 411f842; el motor admite además el modelo remoto optativo.
    from pathlib import Path
    raiz = Path(__file__).parents[1]
    esperado = json.loads((raiz / 'tests/fixtures/referencia_v31.json').read_text())
    parametros = asdict(Configuracion())
    assert parametros.pop('LATENCIA_VELAS') == 0
    assert parametros == esperado['parametros_v31']
    for path, digest in esperado['codigo_sha256'].items():
        assert hashlib.sha256((raiz / path).read_bytes()).hexdigest() == digest


def test_extremo_previo_al_fill_no_dispara_stop_retroactivo():
    q = quotes(precios=(100, 50, 100, 100),
               horas=('09:31:00', '09:31:00.100', '09:31:01', '15:59:00'))
    a = run(q)
    assert a.operaciones.iloc[0].motivo_salida == 'CIERRE_PROGRAMADO'
    assert a.operaciones.iloc[0].entrada_timestamp == t('09:31:01')


def test_reserva_riesgo_y_tres_posiciones_pendientes():
    q = pd.concat([quotes().assign(symbol=s) for s in ['A', 'B', 'C', 'D']])
    s = pd.concat([senales().assign(symbol=s, ATR_14=10.) for s in ['A', 'B', 'C', 'D']])
    a = run(q, signals=s)
    assert len(a.ordenes[a.ordenes.estado.eq('EJECUTADA')]) == 3
    assert a.ordenes.iloc[-1].motivo == 'MAX_POSICIONES'
    assert a.ordenes.riesgo_presupuestado.sum() <= Configuracion().CAPITAL_INICIAL * Configuracion().RIESGO_TOTAL


def test_comparacion_sintetica_preserva_resultados_v31():
    from pathlib import Path
    from trading_ia.comparar_ejecucion import comparar
    resultado = comparar()
    referencia = json.loads((Path(__file__).parent / 'fixtures/resultados_v31_ejecucion.json').read_text())
    assert [x['v31'] for x in resultado['escenarios']] == referencia
    # La latencia no siempre empeora el resultado: el movimiento puede favorecerlo.
    deltas = [x['delta_pnl_latencia_menos_v31'] for x in resultado['escenarios'][:3]]
    assert min(deltas) < 0 < max(deltas)


def test_sesion_multiple_exige_separacion_explicita():
    q = quotes()
    q.loc[q.index[-1], 'timestamp'] += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match='separar fechas'):
        run(q)


def test_gap_supera_riesgo_sin_recortar_perdidas_a_posteriori():
    a = run(quotes(precios=(100, 100, 95, 95)))
    assert a.operaciones.iloc[0].R_presupuestado < -1


def test_no_redimensiona_cantidad_para_ajustar_capital_al_fill():
    a = run(quotes(precios=(100, 200, 201, 202)))
    orden = a.ordenes.iloc[0]
    assert orden.nocional_al_fill > orden.nocional_presupuestado
    assert orden.exceso_nocional_sobre_reserva > 0
    assert orden.estado == 'EJECUTADA'


def test_fill_exacto_en_llegada_es_admisible_y_no_antes():
    q = quotes(precios=(100, 110, 100), horas=('09:31:00', '09:31:00.500', '15:59:00'))
    a = run(q)
    assert a.ordenes.iloc[0].entrada_timestamp == a.ordenes.iloc[0].llegada_timestamp


def test_cierre_anticipado_segun_calendario():
    s = senales()
    q = quotes(precios=(100, 100, 100), horas=('09:31:00', '09:31:01', '12:59:00'))
    # Localizar por fecha en NY para conservar la hora civil.
    for frame in [s, q]:
        locales = frame.timestamp.dt.tz_convert('America/New_York')
        frame['timestamp'] = pd.to_datetime(['2026-11-27 ' + x.strftime('%H:%M:%S') for x in locales]).tz_localize('America/New_York').tz_convert('UTC')
    a = run(q, signals=s)
    assert a.operaciones.iloc[0].motivo_salida == 'CIERRE_PROGRAMADO'
    assert a.operaciones.iloc[0].salida_timestamp.tz_convert('America/New_York').strftime('%H:%M') == '12:59'


def test_ninguna_cotizacion_futura_modifica_orden_ya_ejecutada():
    q = quotes()
    a = run(q.iloc[:2])
    q.loc[q.index[2:], ['bid', 'ask']] = 500
    b = run(q)
    pd.testing.assert_frame_equal(a.ordenes, b.ordenes)


def test_no_mezclar_latencia_por_velas_y_por_cotizaciones():
    with pytest.raises(ValueError, match='No mezclar'):
        run(config=replace(Configuracion(), LATENCIA_VELAS=1))


@pytest.mark.parametrize('atr', [None, float('nan'), 0, -1, float('inf'), -float('inf')])
def test_nueva_senal_con_atr_invalido_no_desaparece_en_silencio(atr):
    s = senales().copy()
    s.loc[0, 'ATR_14'] = atr
    with pytest.raises(ValueError, match='Distancia ATR inválida'):
        preparar_intenciones(s)


def test_no_trade_de_calentamiento_acepta_atr_ausente():
    s = pd.concat([
        senales().assign(timestamp=t('09:29:00'), SENAL='NO TRADE', ATR_14=float('nan')),
        senales(),
    ], ignore_index=True)
    resultado = preparar_intenciones(s)
    assert len(resultado) == 1
    assert resultado.iloc[0]['SENAL'] == 'LONG'


@pytest.mark.parametrize('simbolo', [None, '', '   '])
def test_simbolos_invalidos_no_se_descartan_en_preparacion(simbolo):
    s = senales().copy()
    s.loc[0, 'symbol'] = simbolo
    with pytest.raises(ValueError, match='Símbolo inválido'):
        preparar_intenciones(s)


@pytest.mark.parametrize('categoria', [None, '', 'BUY', 'DESCONOCIDA'])
def test_categorias_de_senal_invalidas_se_rechazan(categoria):
    s = senales().copy()
    s.loc[0, 'SENAL'] = categoria
    with pytest.raises(ValueError, match='Categoría de señal inválida'):
        preparar_intenciones(s)


@pytest.mark.parametrize('simbolo', [None, '', '   '])
def test_simbolos_invalidos_no_se_admiten_en_intenciones_directas(simbolo):
    i = preparar_intenciones(senales())
    i.loc[0, 'symbol'] = simbolo
    with pytest.raises(ValueError, match='Símbolo inválido'):
        simular_latencia(quotes(), i, latencia_ms=500)
