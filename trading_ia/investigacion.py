"""Pipeline local reproducible. Nunca descarga datos ni envía órdenes."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import subprocess
import traceback


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ejecutar(dataset, esperado, salida, procedencia, modelo_ejecucion='v31'):
    """Exige directorio nuevo; persiste diagnóstico incluso si faltan dependencias."""
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=False)
    reporte = {'inicio_utc': datetime.now(timezone.utc).isoformat(), 'schema_version': 1, 'estado': 'ERROR', 'python': platform.python_version(),
               'dependencias': sorted(f'{d.metadata["Name"]}=={d.version}' for d in distributions()),
               'procedencia': procedencia, 'sha256_esperado': esperado, 'modelo_ejecucion': modelo_ejecucion, 'etapa': 'identidad'}
    try:
        reporte['sha256_observado'] = sha256(dataset)
        if reporte['sha256_observado'] != esperado.lower():
            raise ValueError('SHA-256 no coincide')
        raiz = Path(__file__).resolve().parents[1]
        reporte['git_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=raiz, text=True).strip()
        reporte['git_dirty'] = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=raiz, text=True).strip())
        reporte['requirements_sha256'] = sha256(raiz / 'requirements-lock.txt')
        reporte['codigo_sha256'] = {str(p.relative_to(raiz)): sha256(p) for p in sorted((raiz / 'trading_ia').glob('*.py'))}
        reporte['etapa'] = 'dependencias'
        import pandas as pd
        from .backtest import Configuracion, simular
        from .ejecucion import preparar_diferido
        from .calendario import anotar_sesion
        from .calidad_datos import validar_ohlcv, POLITICA_EXTENDIDO_ALPACA
        from .transformaciones import calcular_indicadores, analizar, preparar
        if modelo_ejecucion not in ('v31', 'diferido_1m'):
            raise ValueError('Modelo de ejecución desconocido')
        configuracion = Configuracion(LATENCIA_VELAS=1 if modelo_ejecucion == 'diferido_1m' else 0)
        reporte['parametros'] = asdict(configuracion)
        reporte['estrategia'] = {'atr_stop': 1.5, 'objetivo_nominal_r': 2, 'indicadores_entre_sesiones': True,
                                 'ajuste_splits': 'sin transformacion; requiere revision de procedencia'}
        reporte['etapa'] = 'calidad_original'
        df = pd.read_parquet(dataset)
        if isinstance(df.index, pd.MultiIndex) or df.index.name is not None:
            df = df.reset_index()
        calidad = validar_ohlcv(df, comprobar_cobertura=False, politica_sesion=POLITICA_EXTENDIDO_ALPACA)
        reporte['calidad_original'] = calidad.a_dict()
        if not calidad.valido:
            raise ValueError('Integridad original inválida')
        df['timestamp'] = pd.to_datetime(df.timestamp, utc=True)
        df = df[anotar_sesion(df.timestamp)['en_horario'].to_numpy()].copy()
        reporte['etapa'] = 'calidad_regular'
        calidad = validar_ohlcv(df)
        reporte['calidad_regular'] = calidad.a_dict()
        if df.empty or not calidad.apto_indicadores:
            raise ValueError('Sesiones regulares incompletas o inválidas')
        df = df.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
        df['fecha'] = df.timestamp.dt.tz_convert('America/New_York').dt.date
        def transformar(frame, funcion):
            return pd.concat([funcion(g) for _, g in frame.groupby('symbol', sort=True)], ignore_index=True)
        reporte['etapa'] = 'transformaciones'
        indicadores = transformar(df, calcular_indicadores)
        senales = transformar(indicadores, analizar)
        candidatas = transformar(senales, preparar_diferido if modelo_ejecucion == 'diferido_1m' else preparar)
        reporte['etapa'] = 'backtest'
        resultados = simular(senales, candidatas, configuracion)
        repetidos = simular(senales, candidatas, configuracion)
        for a, b in zip(resultados, repetidos):
            pd.testing.assert_frame_equal(a, b, check_exact=True)
        reporte['determinismo_backtest'] = 'dos ejecuciones idénticas en memoria'
        artefactos = dict(zip(['operaciones', 'rechazos', 'capital'], resultados))
        artefactos.update(indicadores=indicadores, senales=senales, candidatas=candidatas)
        reporte['artefactos'] = {}
        for nombre, tabla in artefactos.items():
            path = salida / f'{nombre}.parquet'
            tabla.to_parquet(path, index=False)
            reporte['artefactos'][nombre] = {'filas': len(tabla), 'sha256': sha256(path)}
        reporte['estado'] = 'OK'
        reporte['etapa'] = 'completado'
    except Exception as error:
        reporte['error_tipo'] = type(error).__name__
        # Trazas y mensajes pueden contener rutas locales: mantener este reporte privado.
        reporte['error'] = str(error)
        reporte['traza'] = traceback.format_exc()
    finally:
        reporte['fin_utc'] = datetime.now(timezone.utc).isoformat()
        (salida / 'ejecucion.json').write_text(json.dumps(reporte, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    return 0 if reporte['estado'] == 'OK' else 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset', type=Path)
    p.add_argument('--sha256', required=True)
    p.add_argument('--salida', type=Path, required=True)
    p.add_argument('--procedencia', required=True, help='JSON local con dataset_id, fuente, licencia, ajuste y tipo (real/sintetico)')
    p.add_argument('--modelo-ejecucion', choices=['v31', 'diferido_1m'], default='v31', help='v31 es el baseline; diferido_1m fija niveles al cierre y entra una vela adicional después')
    a = p.parse_args()
    meta = json.loads(Path(a.procedencia).read_text())
    if any(not meta.get(k) for k in ['dataset_id', 'fuente', 'licencia', 'ajuste', 'tipo']):
        p.error('Procedencia incompleta')
    if meta['tipo'] not in ['real', 'sintetico']:
        p.error('tipo debe ser real o sintetico')
    return ejecutar(a.dataset, a.sha256, a.salida, meta, a.modelo_ejecucion)


if __name__ == '__main__':
    raise SystemExit(main())
