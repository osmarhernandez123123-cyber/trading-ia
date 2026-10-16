"""Ejecución offline identificada por SHA-256. Nunca descarga ni envía órdenes."""
from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import shutil
import subprocess

import pandas as pd
from .backtest import Configuracion, simular
from .calidad_datos import sha256_archivo, escribir_json, validar_ohlcv, exigir_integridad_original
from .etapas import indicadores, senales, candidatas


def huella_tabla(df):
    """Hash lógico, independiente de la codificación Parquet; columnas y orden cuentan."""
    contenido = df.to_json(orient='table', date_format='iso', date_unit='ns', double_precision=15)
    return hashlib.sha256(contenido.encode()).hexdigest()


def ejecutar(dataset, sha256, salida, *, fuente, licencia, ajustes, sintetico=False):
    dataset, salida = Path(dataset).resolve(), Path(salida).resolve()
    salida.mkdir(parents=True, exist_ok=False)
    registro = {'schema_version': 1, 'estado': 'iniciado',
                'inicio_utc': datetime.now(timezone.utc).isoformat(),
                'dataset_sha256_esperado': sha256, 'fuente': fuente, 'licencia': licencia,
                'ajustes': ajustes, 'datos_sinteticos': sintetico,
                'configuracion': asdict(Configuracion()),
                'estrategia': {'ATR_stop': 1.5, 'objetivo_R_nominal': 2,
                              'indicadores_entre_sesiones': True,
                              'EMA': [9, 21], 'RSI_Wilder': 14, 'ATR_Wilder': 14,
                              'volumen_relativo_ventana': 20, 'volumen_relativo_minimo': 1,
                              'RSI_LONG': [50, 70], 'RSI_SHORT': [30, 50],
                              'VWAP': 'diario', 'entrada': 'apertura siguiente minuto'},
                'python': platform.python_version(),
                'paquetes': dict(sorted((d.metadata['Name'], d.version) for d in importlib.metadata.distributions())),
                'etapas': [], 'advertencias': []}
    codigo = Path(__file__).resolve().parent.parent
    revision = subprocess.run(['git', '-C', str(codigo), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    registro['git_commit'] = revision.stdout.strip()
    registro['git_dirty'] = bool(subprocess.run(['git', '-C', str(codigo), 'status', '--porcelain'], capture_output=True, text=True).stdout)
    registro['codigo_sha256'] = {str(p.relative_to(codigo)): sha256_archivo(p)
                               for p in sorted(codigo.rglob('*.py'))
                               if '.venv' not in p.parts and '.git' not in p.parts}
    log = io.StringIO()
    try:
        if not fuente.strip() or not licencia.strip():
            raise ValueError('Fuente y licencia/autorización documentada obligatorias')
        if ajustes not in {'raw', 'split', 'all'}:
            raise ValueError('Declarar ajustes raw, split o all según la fuente')
        # Congelar los bytes consumidos evita cambios concurrentes en el archivo original.
        snapshot = salida / 'dataset.parquet'
        shutil.copyfile(dataset, snapshot)
        observado = sha256_archivo(snapshot)
        registro['dataset_sha256'] = observado
        if observado != sha256.lower():
            raise ValueError('SHA-256 no coincide; no se ejecutó el pipeline')
        df = pd.read_parquet(snapshot)
        if not {'symbol', 'timestamp'} <= set(df.columns):
            df = df.reset_index()
        with contextlib.redirect_stdout(log):
            original = exigir_integridad_original(df, 'investigacion')
            escribir_json(original.a_dict(), salida / 'calidad_original.json')
            registro['filas_originales'] = len(df)
            ind = indicadores(df)
            registro['filas_regulares'] = len(ind)
            registro['filas_extendidas_excluidas'] = len(df) - len(ind)
            calidad = validar_ohlcv(ind)
            escribir_json(calidad.a_dict(), salida / 'calidad.json')
            registro['advertencias'].extend(x.descripcion for x in calidad.incidencias if x.gravedad == 'ADVERTENCIA')
            if any(x.codigo == 'SALTO_PRECIO' for x in calidad.incidencias):
                raise ValueError('Salto de precio requiere revisión de corporate actions antes de simular')
            sig = senales(ind)
            cand = candidatas(sig)
            res, rech, curva = simular(sig, cand)
            tablas = dict(indicadores=ind, senales=sig, candidatas=cand,
                          operaciones=res, rechazos=rech, capital=curva)
            for nombre, tabla in tablas.items():
                tabla.to_parquet(salida / f'{nombre}.parquet', index=False)
                registro['etapas'].append({'nombre': nombre, 'filas': len(tabla),
                                          'sha256_logico': huella_tabla(tabla),
                                          'sha256_archivo': sha256_archivo(salida / f'{nombre}.parquet')})
        registro.update(estado='completado', operaciones=len(res),
                        pnl_usd=float(res.pnl_usd.sum()),
                        patrimonio_final=float(curva.patrimonio.iloc[-1]))
        if res.empty:
            registro['advertencias'].append('Sin operaciones: resultado válido de estrategia, no fallo de infraestructura')
        if ajustes == 'raw':
            registro['advertencias'].append('Precios raw: splits y dividendos no se resuelven automáticamente')
    except Exception as error:
        registro.update(estado='error', error={'tipo': type(error).__name__, 'mensaje': str(error)})
        raise
    finally:
        registro['fin_utc'] = datetime.now(timezone.utc).isoformat()
        (salida / 'ejecucion.log').write_text(log.getvalue())
        escribir_json(registro, salida / 'ejecucion.json')
    return registro


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset')
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--salida', required=True)
    parser.add_argument('--fuente', required=True)
    parser.add_argument('--licencia', required=True)
    parser.add_argument('--ajustes', required=True, choices=['raw', 'split', 'all'])
    parser.add_argument('--sintetico', action='store_true')
    args = vars(parser.parse_args())
    try:
        ejecutar(**args)
    except Exception as error:
        parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()
