
import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent
VELAS = BASE / "datos_senales.parquet"
CANDIDATAS = BASE / "entradas_candidatas.parquet"
SALIDA = BASE / "resultados_backtesting_v3.parquet"
RECHAZOS = BASE / "rechazos_backtesting_v3.parquet"
CURVA = BASE / "capital_backtesting_v3.parquet"

CAPITAL_INICIAL = 100_000.0
RIESGO_OPERACION = 0.01
RIESGO_TOTAL = 0.03
MAX_POSICIONES = 3

SLIPPAGE_BPS = 2.0
COMISION_ACCION = 0.0
ZONA = "America/New_York"

# Hipotesis: acciones enteras, sin apalancamiento,
# sin posiciones overnight, y capital inicial en USD.
# No se incluyen intereses, dividendos ni impuestos.

velas = pd.read_parquet(VELAS).reset_index(drop=True)
candidatas = pd.read_parquet(CANDIDATAS).reset_index(drop=True)

for nombre, df in [("velas", velas), ("candidatas", candidatas)]:
    necesarias = {"symbol", "timestamp"}
    if nombre == "velas":
        necesarias |= {"open", "high", "low", "close"}
    else:
        necesarias |= {
            "entrada_timestamp", "SENAL",
            "stop_loss", "take_profit"
        }
    faltan = necesarias - set(df.columns)
    if faltan:
        raise ValueError(f"{nombre}: faltan {faltan}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    if df.duplicated(["symbol", "timestamp"]).any():
        raise ValueError(f"{nombre}: timestamps duplicados")

candidatas["entrada_timestamp"] = pd.to_datetime(
    candidatas["entrada_timestamp"], utc=True
)

velas = velas.sort_values(["timestamp", "symbol"]).copy()

local = velas["timestamp"].dt.tz_convert(ZONA)
minutos = local.dt.hour * 60 + local.dt.minute

velas = velas[
    (minutos >= 570) & (minutos < 960)
].copy()

velas["fecha"] = (
    velas["timestamp"].dt.tz_convert(ZONA).dt.date
)

# Candidatas generadas una vela antes.
diferencia = (
    candidatas["entrada_timestamp"] - candidatas["timestamp"]
).dt.total_seconds()

candidatas = candidatas[diferencia.eq(60)].copy()

if candidatas.duplicated(
    ["symbol", "entrada_timestamp"]
).any():
    raise ValueError("Entradas candidatas duplicadas")

indice = {
    (r.symbol, r.entrada_timestamp): r
    for r in candidatas.itertuples(index=False)
}

# Identificar la ultima vela disponible de cada sesion.
velas["ultima_sesion"] = (
    velas.groupby(["symbol", "fecha"])["timestamp"]
    .transform("max")
    .eq(velas["timestamp"])
)

# Comprobar precios y consistencia OHLC.
numericas = ["open", "high", "low", "close"]
if not np.isfinite(velas[numericas].to_numpy(dtype=float)).all():
    raise ValueError("Hay precios no finitos")

if (
    (velas[numericas] <= 0).any().any()
    or (velas["high"] < velas[["open", "close", "low"]].max(axis=1)).any()
    or (velas["low"] > velas[["open", "close", "high"]].min(axis=1)).any()
):
    raise ValueError("Existen velas OHLC invalidas")

capital = CAPITAL_INICIAL
efectivo = CAPITAL_INICIAL
activas = {}
operaciones = []
rechazos = []
curva = []

def precio_ejecucion(precio, direccion, entrada):
    signo = (1 if direccion == "LONG" else -1)
    if not entrada:
        signo *= -1
    return float(precio) * (1 + signo * SLIPPAGE_BPS / 10000)

def patrimonio(precios):
    total = efectivo
    for simbolo, p in activas.items():
        precio = precios.get(simbolo, p["ultimo_close"])
        signo = 1 if p["direccion"] == "LONG" else -1
        total += signo * p["acciones"] * precio
    return total

def riesgo_abierto():
    return sum(p["riesgo_total"] for p in activas.values())

def cerrar(simbolo, precio_base, momento, motivo):
    global capital, efectivo

    p = activas.pop(simbolo)
    salida = precio_ejecucion(
        precio_base, p["direccion"], False
    )
    cantidad = p["acciones"]
    signo = 1 if p["direccion"] == "LONG" else -1

    efectivo += signo * cantidad * salida
    efectivo -= cantidad * COMISION_ACCION

    pnl = (
        signo * (salida - p["entrada"]) * cantidad
        - 2 * COMISION_ACCION * cantidad
    )

    capital += pnl
    p.update(
        salida=salida,
        salida_timestamp=momento,
        motivo_salida=motivo,
        pnl_usd=pnl,
        R=pnl / p["riesgo_total"],
        capital_cierre=capital
    )
    operaciones.append(p)

def rechazar(simbolo, momento, motivo):
    rechazos.append({
        "symbol": simbolo,
        "entrada_timestamp": momento,
        "motivo": motivo
    })

# Procesamiento cronologico: todas las acciones por minuto.
for t, bloque in velas.groupby("timestamp", sort=True):
    bloque = bloque.sort_values("symbol")
    precios = {
        v.symbol: float(v.open)
        for v in bloque.itertuples(index=False)
    }

    # 1. Procesar salidas de posiciones ya abiertas.
    bloqueadas = set()

    for v in bloque.itertuples(index=False):
        s = v.symbol
        if s not in activas:
            continue

        p = activas[s]

        # Nunca mantener una posicion hasta la siguiente sesion.
        if v.fecha != p["fecha"]:
            cerrar(
                s, p["ultimo_close"],
                p["ultimo_timestamp"], "FIN_SESION"
            )
            bloqueadas.add(s)
            continue

        sl, tp = p["stop_loss"], p["take_profit"]
        largo = p["direccion"] == "LONG"

        gap_sl = v.open <= sl if largo else v.open >= sl
        gap_tp = v.open >= tp if largo else v.open <= tp
        toca_sl = v.low <= sl if largo else v.high >= sl
        toca_tp = v.high >= tp if largo else v.low <= tp

        if gap_sl:
            cerrar(s, v.open, t, "GAP_STOP")
        elif gap_tp:
            cerrar(s, v.open, t, "GAP_TP")
        elif toca_sl:
            cerrar(s, sl, t, "STOP_LOSS")
        elif toca_tp:
            cerrar(s, tp, t, "TAKE_PROFIT")
        else:
            p["ultimo_close"] = float(v.close)
            p["ultimo_timestamp"] = t

        if s not in activas:
            bloqueadas.add(s)

    # 2. Evaluar nuevas entradas.
    for v in bloque.itertuples(index=False):
        s = v.symbol
        c = indice.get((s, t))

        if c is None:
            continue

        motivo = None

        if s in activas or s in bloqueadas:
            motivo = "POSICION_EXISTENTE"
        elif v.ultima_sesion:
            motivo = "ULTIMA_VELA_SESION"
        elif len(activas) >= MAX_POSICIONES:
            motivo = "MAX_POSICIONES"
        elif c.SENAL not in ("LONG", "SHORT"):
            motivo = "DIRECCION_INVALIDA"
        elif not np.isfinite(
            [c.stop_loss, c.take_profit]
        ).all():
            motivo = "NIVELES_INVALIDOS"

        if motivo:
            rechazar(s, t, motivo)
            continue

        direccion = c.SENAL
        signo = 1 if direccion == "LONG" else -1

        entrada = precio_ejecucion(v.open, direccion, True)
        sl = float(c.stop_loss)
        tp = float(c.take_profit)

        if not (
            (sl < entrada < tp) if signo == 1
            else (tp < entrada < sl)
        ):
            rechazar(s, t, "NIVELES_INVALIDOS")
            continue

        # Riesgo unitario presupuestado incluyendo
        # slippage estimado en el stop y dos comisiones.
        salida_stop = precio_ejecucion(sl, direccion, False)
        riesgo_unitario = (
            signo * (entrada - salida_stop)
            + 2 * COMISION_ACCION
        )

        if riesgo_unitario <= 0:
            rechazar(s, t, "RIESGO_INVALIDO")
            continue

        # Capital de referencia marcado a mercado.
        equity = patrimonio(precios)

        presupuesto = min(
            max(0.0, equity * RIESGO_OPERACION),
            max(0.0, equity * RIESGO_TOTAL - riesgo_abierto())
        )

        por_riesgo = int(
            np.floor(presupuesto / riesgo_unitario)
        )

        # Para LONG reservar efectivo.
        # Para SHORT reservar colateral equivalente
        # al nocional y no reutilizar ingresos de la venta.
        reservado = sum(
            p["nocional"] for p in activas.values()
        )

        capacidad = max(0.0, capital - reservado)
        por_capital = int(
            np.floor(capacidad / (entrada + COMISION_ACCION))
        )

        acciones = min(por_riesgo, por_capital)

        if acciones < 1:
            rechazar(s, t, "CAPITAL_O_RIESGO_INSUFICIENTE")
            continue

        nocional = acciones * entrada
        riesgo_total = acciones * riesgo_unitario

        efectivo -= signo * nocional
        efectivo -= acciones * COMISION_ACCION

        activas[s] = {
            "symbol": s,
            "fecha": v.fecha,
            "direccion": direccion,
            "senal_timestamp": c.timestamp,
            "entrada_timestamp": t,
            "entrada": entrada,
            "stop_loss": sl,
            "take_profit": tp,
            "acciones": acciones,
            "nocional": nocional,
            "riesgo_unitario": riesgo_unitario,
            "riesgo_total": riesgo_total,
            "ultimo_close": float(v.close),
            "ultimo_timestamp": t
        }

        # La vela de entrada puede tocar SL y TP.
        # Ante ambiguedad, se prioriza el stop.
        toca_sl = v.low <= sl if signo == 1 else v.high >= sl
        toca_tp = v.high >= tp if signo == 1 else v.low <= tp

        if toca_sl:
            cerrar(s, sl, t, "STOP_LOSS_ENTRADA")
        elif toca_tp:
            cerrar(s, tp, t, "TAKE_PROFIT_ENTRADA")

    # 3. Cerrar al terminar la sesion disponible.
    for v in bloque.itertuples(index=False):
        if v.ultima_sesion and v.symbol in activas:
            cerrar(v.symbol, v.close, t, "FIN_SESION")

    # 4. Registrar patrimonio al cierre del minuto.
    cierres = {
        v.symbol: float(v.close)
        for v in bloque.itertuples(index=False)
    }

    equity = patrimonio(cierres)

    curva.append({
        "timestamp": t,
        "capital_realizado": capital,
        "patrimonio": equity,
        "posiciones_abiertas": len(activas)
    })

# Cerrar cualquier posicion residual.
for s in list(activas):
    p = activas[s]
    cerrar(
        s, p["ultimo_close"],
        p["ultimo_timestamp"], "FIN_DATOS"
    )

res = pd.DataFrame(operaciones)

if res.empty:
    raise RuntimeError("No se generaron operaciones")

res = res.sort_values(
    ["salida_timestamp", "symbol"]
).reset_index(drop=True)

rech = pd.DataFrame(
    rechazos,
    columns=["symbol", "entrada_timestamp", "motivo"]
)

capital_df = pd.DataFrame(curva).sort_values("timestamp")
capital_df["maximo"] = (
    capital_df["patrimonio"].cummax().clip(lower=CAPITAL_INICIAL)
)
capital_df["drawdown_pct"] = (
    capital_df["patrimonio"] / capital_df["maximo"] - 1
) * 100

res.to_parquet(SALIDA, index=False)
rech.to_parquet(RECHAZOS, index=False)
capital_df.to_parquet(CURVA, index=False)

ganancias = res.loc[res.pnl_usd > 0, "pnl_usd"].sum()
perdidas = abs(res.loc[res.pnl_usd < 0, "pnl_usd"].sum())
pf = ganancias / perdidas if perdidas > 0 else float("inf")

print("\n=== BACKTESTING V3 ===")
print("Capital inicial: $", round(CAPITAL_INICIAL, 2))
print("Capital final: $", round(capital, 2))
print("Rentabilidad: ", round(
    (capital / CAPITAL_INICIAL - 1) * 100, 2
), "%")
print("Operaciones:", len(res))
print("Win rate:", round((res.R > 0).mean() * 100, 2), "%")
print("R promedio:", round(res.R.mean(), 4))
print("Profit factor:", round(pf, 3))
print("Max drawdown:", round(
    capital_df.drawdown_pct.min(), 2
), "%")

print("\n=== POR ACCION ===")
print(res.groupby("symbol")["pnl_usd"].agg(
    ["count", "sum", "mean"]
).round(2))

print("\n=== MOTIVOS DE SALIDA ===")
print(res.motivo_salida.value_counts())

print("\n=== RECHAZOS ===")
print(rech.motivo.value_counts())

print("\nArchivos creados:")
print(SALIDA.name)
print(RECHAZOS.name)
print(CURVA.name)
