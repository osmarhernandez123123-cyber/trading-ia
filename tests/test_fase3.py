"""Exclusivamente fixtures sintéticos; no son validación histórica."""
from datetime import datetime, timedelta, timezone
import json

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from trading_ia.backtest import simular
from trading_ia.calendario import minutos_esperados
from trading_ia.calidad_datos import sha256_archivo, validar_ohlcv
from trading_ia.etapas import indicadores, senales, candidatas
from trading_ia.eventos import Evento
from trading_ia.investigacion import ejecutar


def fixture():
    t = minutos_esperados('2026-01-05')
    x = 100 + np.sin(np.arange(len(t)) / 6) * .5 + np.arange(len(t)) * .002
    return pd.DataFrame(dict(symbol='TEST', timestamp=t, open=x, high=x+.2,
                             low=x-.2, close=x+.01, volume=1000))


def test_dos_ejecuciones_identicas_y_contabilidad(tmp_path):
    path = tmp_path / 'sintetico.parquet'
    fixture().to_parquet(path, index=False)
    kwargs = dict(fuente='fixture sintético', licencia='prueba', ajustes='raw', sintetico=True)
    a = ejecutar(path, sha256_archivo(path), tmp_path/'a', **kwargs)
    b = ejecutar(path, sha256_archivo(path), tmp_path/'b', **kwargs)
    assert a['estado'] == b['estado'] == 'completado'
    assert a['operaciones'] > 0
    assert [x['sha256_logico'] for x in a['etapas']] == [x['sha256_logico'] for x in b['etapas']]
    assert a['patrimonio_final'] == pytest.approx(100000 + a['pnl_usd'])


def test_sin_operaciones_es_resultado_valido():
    df = fixture().assign(open=100., high=100., low=100., close=100.)
    sig = senales(indicadores(df))
    res, rech, curva = simular(sig, candidatas(sig))
    assert res.empty and rech.empty
    assert curva.patrimonio.eq(100000).all()


def test_futuro_no_cambia_indicadores_ni_senales():
    df = fixture()
    cambiado = df.copy()
    cambiado.loc[200:, ['open','high','low','close']] *= 1.1
    a, b = senales(indicadores(df)), senales(indicadores(cambiado))
    assert_frame_equal(a.iloc[:200], b.iloc[:200])
    ca, cb = candidatas(a), candidatas(b)
    limite = a.timestamp.iloc[199]
    assert_frame_equal(ca[ca.entrada_timestamp <= limite], cb[cb.entrada_timestamp <= limite])


def test_sha_incorrecto_deja_error_sin_resultados(tmp_path):
    path = tmp_path/'datos.parquet'
    fixture().to_parquet(path)
    out = tmp_path/'fallo'
    with pytest.raises(ValueError, match='SHA-256'):
        ejecutar(path, '0'*64, out, fuente='synthetic', licencia='test', ajustes='raw', sintetico=True)
    registro = json.loads((out/'ejecucion.json').read_text())
    assert registro['estado'] == 'error'
    assert not (out/'operaciones.parquet').exists()


@pytest.mark.parametrize('defecto', ['duplicado','gap','incompleta','split','minuto','simbolo','vacio'])
def test_defectos_no_pasan_silenciosamente(defecto):
    df = fixture()
    if defecto == 'duplicado': df = pd.concat([df, df.iloc[[0]]])
    if defecto == 'gap': df = df.drop(100)
    if defecto == 'incompleta': df = df.iloc[:-1]
    if defecto == 'split': df.loc[200:, ['open','high','low','close']] *= .25
    if defecto == 'minuto': df['timestamp'] += pd.Timedelta(seconds=1)
    if defecto == 'simbolo': df.loc[0, 'symbol'] = None
    if defecto == 'vacio': df = df.iloc[:0]
    reporte = validar_ohlcv(df)
    if defecto == 'split':
        assert any(x.codigo == 'SALTO_PRECIO' for x in reporte.incidencias)
    else:
        assert not reporte.valido


def test_eventos_solo_disponibles_despues_de_ingesta():
    t = datetime(2026, 1, 5, tzinfo=timezone.utc)
    e = Evento('id', 'macro', 'fuente', t, t+timedelta(seconds=5), t+timedelta(seconds=8), 'a'*64)
    assert not e.visible(t+timedelta(seconds=7))
    assert e.visible(t+timedelta(seconds=8))
    with pytest.raises(ValueError, match='Orden'):
        Evento('id', 'macro', 'fuente', t, t-timedelta(seconds=1), t, 'a'*64)


def test_salto_bloquea_ejecucion_investigacion(tmp_path):
    df = fixture()
    df.loc[200:, ['open', 'high', 'low', 'close']] *= .25
    path = tmp_path/'split.parquet'
    df.to_parquet(path)
    with pytest.raises(ValueError, match='corporate actions'):
        ejecutar(path, sha256_archivo(path), tmp_path/'salida', fuente='fixture', licencia='test', ajustes='raw', sintetico=True)
    assert not (tmp_path/'salida/operaciones.parquet').exists()


def test_candidata_sin_entrada_no_se_pierde_silenciosamente():
    sig = senales(indicadores(fixture()))
    cand = candidatas(sig)
    cand.loc[cand.index[0], 'entrada_timestamp'] += pd.Timedelta(minutes=1)
    with pytest.raises(ValueError, match='60 segundos'):
        simular(sig, cand)
