"""Manifiesto declarativo de procedencia de un reporte de cobertura local.

No abre datasets, no accede a red ni acredita licencias o procedencia por sí solo.
El SHA del dataset procede del reporte de cobertura previamente generado.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import math
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .calendario import ZONA_NY, horario_sesiones


def _entero(obj: dict, campo: str) -> int:
    valor = obj.get(campo)
    if type(valor) is not int or valor < 0:
        raise ValueError(f"Conteo inválido: {campo}")
    return valor


def _validar_conteos(obj: dict) -> None:
    esperados = _entero(obj, "minutos_esperados")
    presentes = _entero(obj, "minutos_presentes")
    faltantes = _entero(obj, "minutos_faltantes")
    if presentes > esperados or faltantes != esperados - presentes or esperados == 0:
        raise ValueError("Conteos de cobertura inconsistentes")
    fraccion = obj.get("fraccion_cobertura")
    if (type(fraccion) not in (float, int) or not math.isfinite(fraccion)
            or not 0 <= fraccion <= 1
            or not math.isclose(fraccion, presentes / esperados, abs_tol=0.00000051)):
        raise ValueError("Fracción de cobertura inconsistente")



def _fecha_iso(valor, nombre: str) -> date:
    """Exige YYYY-MM-DD canónico; no interpreta fechas ambiguas."""
    if not isinstance(valor, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", valor) is None:
        raise ValueError(f"Fecha {nombre} inválida")
    try:
        fecha = date.fromisoformat(valor)
    except ValueError as exc:
        raise ValueError(f"Fecha {nombre} inválida") from exc
    if fecha.isoformat() != valor:
        raise ValueError(f"Fecha {nombre} inválida")
    return fecha


def _validar_calendario_y_sesiones(reporte: dict, simbolos: list, sesiones: list, resumen: dict) -> None:
    """Contrasta calendario, fechas y cierres con sesiones bursátiles reales."""
    calendario = reporte.get("calendario")
    if calendario not in ("XNYS", "XNAS"):
        raise ValueError("Calendario de cobertura inválido")
    if reporte.get("zona_sesion") != ZONA_NY:
        raise ValueError("Zona de sesión inconsistente")
    inicio = _fecha_iso(reporte.get("inicio"), "inicio")
    fin = _fecha_iso(reporte.get("fin"), "fin")
    if inicio > fin:
        raise ValueError("Rango de fechas invertido")
    horario = horario_sesiones(inicio, fin, calendario)
    if horario.empty or len(horario) != resumen["sesiones_por_simbolo"]:
        raise ValueError("Fechas y número de sesiones no coinciden con calendario")

    fechas_esperadas = set(horario.index)
    fechas_por_simbolo = {fila["symbol"]: set() for fila in simbolos}
    completas = {nombre: 0 for nombre in fechas_por_simbolo}
    sin_datos = {nombre: 0 for nombre in fechas_por_simbolo}
    for fila in sesiones:
        fecha = _fecha_iso(fila.get("fecha"), "sesión")
        if fecha not in fechas_esperadas:
            raise ValueError("Fecha de sesión fuera del calendario declarado")
        esperado = horario.loc[fecha]
        if fila["minutos_esperados"] != int(esperado["minutos_esperados"]):
            raise ValueError("Minutos esperados incompatibles con calendario")
        if type(fila.get("cierre_anticipado")) is not bool or (
            fila["cierre_anticipado"] != bool(esperado["cierre_anticipado"])
        ):
            raise ValueError("Cierre anticipado incompatible con calendario")
        presentes = fila["minutos_presentes"]
        faltantes = fila["minutos_faltantes"]
        estado = (
            "sin_datos" if presentes == 0 else
            "completa_cierre_anticipado" if faltantes == 0 and esperado["cierre_anticipado"] else
            "completa" if faltantes == 0 else "incompleta"
        )
        if fila.get("estado") != estado:
            raise ValueError("Estado de sesión inconsistente")
        nombre = fila["symbol"]
        fechas_por_simbolo[nombre].add(fecha)
        completas[nombre] += faltantes == 0
        sin_datos[nombre] += presentes == 0
    for fila in simbolos:
        nombre = fila["symbol"]
        if fechas_por_simbolo[nombre] != fechas_esperadas:
            raise ValueError("Faltan sesiones de calendario por símbolo")
        if (_entero(fila, "sesiones_completas") != completas[nombre] or
                _entero(fila, "sesiones_sin_datos") != sin_datos[nombre]):
            raise ValueError("Conteos de estado por símbolo inconsistentes")


def crear_manifiesto(
    reporte: dict,
    *,
    licencia: str,
    ajuste: str,
    zona_timestamps: str,
    version_dataset: str,
    fuente_esperada: str | None = None,
) -> dict:
    """Vincula declaraciones de procedencia con un reporte agregado verificado."""
    if not isinstance(reporte, dict) or type(reporte.get("schema_version")) is not int or reporte["schema_version"] != 1:
        raise ValueError("Versión del reporte de cobertura no admitida")
    huella = reporte.get("archivo_sha256")
    if not isinstance(huella, str) or re.fullmatch(r"[0-9a-f]{64}", huella) is None:
        raise ValueError("Falta SHA-256 válido del dataset")
    tamano = _entero(reporte, "archivo_bytes")
    if tamano == 0:
        raise ValueError("Tamaño del dataset inválido")
    fuente = reporte.get("fuente")
    if not isinstance(fuente, str) or not fuente.strip():
        raise ValueError("Fuente del reporte ausente")
    if fuente_esperada is not None and fuente != fuente_esperada:
        raise ValueError("Fuente declarada no coincide con el reporte")
    if not isinstance(licencia, str) or not licencia.strip() or len(licencia) > 200:
        raise ValueError("Licencia/permiso de uso debe declararse")
    if ajuste not in ("sin_ajuste", "split", "split_dividendo", "otro"):
        raise ValueError("Política de ajuste no reconocida")
    if not isinstance(zona_timestamps, str):
        raise ValueError("Zona de timestamps inválida")
    try:
        ZoneInfo(zona_timestamps)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError("Zona de timestamps inválida") from exc
    if not isinstance(version_dataset, str) or re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", version_dataset
    ) is None:
        raise ValueError("Versión del dataset inválida")

    resumen = reporte.get("resumen")
    simbolos = reporte.get("por_simbolo")
    sesiones = reporte.get("sesiones")
    if not isinstance(resumen, dict) or not isinstance(simbolos, list) or not isinstance(sesiones, list):
        raise ValueError("Estructura de cobertura incompleta")
    _validar_conteos(resumen)
    if _entero(resumen, "simbolos") != len(simbolos) or not simbolos:
        raise ValueError("Número de símbolos inconsistente")
    sesiones_por_simbolo = _entero(resumen, "sesiones_por_simbolo")
    if sesiones_por_simbolo == 0 or len(sesiones) != len(simbolos) * sesiones_por_simbolo:
        raise ValueError("Número de sesiones inconsistente")

    nombres = set()
    suma = [0, 0, 0]
    for fila in simbolos:
        if not isinstance(fila, dict):
            raise ValueError("Fila de símbolo inválida")
        nombre = fila.get("symbol")
        if not isinstance(nombre, str) or not nombre.strip() or nombre in nombres:
            raise ValueError("Símbolo repetido o inválido")
        nombres.add(nombre)
        _validar_conteos(fila)
        for i, campo in enumerate(("minutos_esperados", "minutos_presentes", "minutos_faltantes")):
            suma[i] += fila[campo]
    if suma != [resumen[x] for x in ("minutos_esperados", "minutos_presentes", "minutos_faltantes")]:
        raise ValueError("Totales por símbolo no coinciden")

    vistos = set()
    por_simbolo = {nombre: [0, 0, 0] for nombre in nombres}
    for fila in sesiones:
        if not isinstance(fila, dict) or fila.get("symbol") not in nombres:
            raise ValueError("Sesión con símbolo inválido")
        clave = (fila["symbol"], fila.get("fecha"))
        if not isinstance(clave[1], str) or clave in vistos:
            raise ValueError("Sesión duplicada o inválida")
        vistos.add(clave)
        _validar_conteos(fila)
        for i, campo in enumerate(("minutos_esperados", "minutos_presentes", "minutos_faltantes")):
            por_simbolo[fila["symbol"]][i] += fila[campo]
    for fila in simbolos:
        if por_simbolo[fila["symbol"]] != [
            fila[x] for x in ("minutos_esperados", "minutos_presentes", "minutos_faltantes")
        ]:
            raise ValueError("Sesiones no coinciden con resumen por símbolo")
    _validar_calendario_y_sesiones(reporte, simbolos, sesiones, resumen)

    return {
        "schema_version": 1,
        "tipo": "manifiesto_procedencia_declarada",
        "version_dataset": version_dataset,
        "fuente_declarada": fuente,
        "licencia_declarada": licencia.strip(),
        "ajuste_declarado": ajuste,
        "zona_timestamps_declarada": zona_timestamps,
        "archivo_sha256": huella,
        "archivo_bytes": tamano,
        "cobertura_schema_version": 1,
        "cobertura": {
            "calendario": reporte.get("calendario"),
            "zona_sesion": reporte.get("zona_sesion"),
            "inicio": reporte.get("inicio"),
            "fin": reporte.get("fin"),
            "resumen": resumen,
        },
        "advertencia": (
            "Metadatos declarados, no verificados contra proveedor ni licencia. "
            "El SHA vincula bytes, no acredita origen ni derechos de redistribución."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reporte", type=Path, required=True, help="JSON de cobertura local")
    parser.add_argument("--salida", type=Path, required=True, help="Nuevo JSON de manifiesto")
    parser.add_argument("--licencia", required=True, help="Declaración de licencia o permiso de uso")
    parser.add_argument("--ajuste", required=True, choices=("sin_ajuste", "split", "split_dividendo", "otro"))
    parser.add_argument("--zona-timestamps", required=True, help="Zona IANA declarada, p. ej. UTC")
    parser.add_argument("--version-dataset", required=True, help="Identificador de versión inmutable")
    parser.add_argument("--fuente-esperada", help="Opcional: debe coincidir con fuente del reporte")
    args = parser.parse_args(argv)
    if args.salida.exists() or args.salida.is_symlink():
        parser.error("El manifiesto de salida ya existe; no se sobrescribe")
    if args.salida.resolve() == args.reporte.resolve():
        parser.error("El manifiesto no puede sobrescribir el reporte")
    datos_reporte = args.reporte.read_bytes()
    reporte = json.loads(datos_reporte)
    manifiesto = crear_manifiesto(
        reporte, licencia=args.licencia, ajuste=args.ajuste,
        zona_timestamps=args.zona_timestamps, version_dataset=args.version_dataset,
        fuente_esperada=args.fuente_esperada,
    )
    manifiesto["reporte_cobertura_sha256"] = hashlib.sha256(datos_reporte).hexdigest()
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("x", encoding="utf-8") as archivo:
        json.dump(manifiesto, archivo, ensure_ascii=False, indent=2, sort_keys=True)
        archivo.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
