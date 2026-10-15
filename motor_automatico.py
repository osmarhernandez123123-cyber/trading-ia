
import fcntl
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
BLOQUEO = CARPETA / ".actualizacion.lock"
LOG = CARPETA / "actualizaciones.log"

def registrar(mensaje):
    fecha = datetime.now().astimezone().isoformat()
    texto = f"[{fecha}] {mensaje}"
    print(texto, flush=True)
    with LOG.open("a", encoding="utf-8") as archivo:
        archivo.write(texto + "\n")

def ejecutar(nombre):
    registrar(f"Iniciando {nombre}")

    resultado = subprocess.run(
        [sys.executable, str(CARPETA / nombre)],
        cwd=CARPETA,
        capture_output=True,
        text=True
    )

    if resultado.stdout:
        registrar(resultado.stdout.strip())

    if resultado.stderr:
        registrar(resultado.stderr.strip())

    if resultado.returncode != 0:
        raise RuntimeError(
            f"{nombre} fallo: {resultado.returncode}"
        )

    registrar(f"{nombre} completado")

with BLOQUEO.open("w") as archivo_bloqueo:
    try:
        fcntl.flock(
            archivo_bloqueo.fileno(),
            fcntl.LOCK_EX | fcntl.LOCK_NB
        )
    except BlockingIOError:
        registrar("Otra actualizacion sigue activa")
        sys.exit(0)

    try:
        registrar("=== CICLO DE ACTUALIZACION ===")
        ejecutar("actualizar_datos.py")
        ejecutar("indicadores.py")
        registrar("Ciclo completado correctamente")
    except Exception as error:
        registrar(f"ERROR: {error}")
        sys.exit(1)
