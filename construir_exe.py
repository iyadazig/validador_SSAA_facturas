# -*- coding: utf-8 -*-
r"""
Genera "Revisor SSAA.exe" en la carpeta del proyecto.

    python construir_exe.py

El ejecutable guarda los datos (contratos_ssaa.json, revisiones_ssaa\) en la carpeta
donde este y lee los Excel de ESIOS de ..\Descarga_datos_ESIOS. No lleva credenciales:
las de Gemweb se buscan en tiempo de ejecucion igual que en la app (ver gemweb.py).
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DESTINO = RAIZ / "Revisor SSAA.exe"


def main():
    inicio = time.time()
    shutil.rmtree(RAIZ / "dist", ignore_errors=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "RevisorSSAA.spec", "--noconfirm",
                    "--log-level", "WARN"], cwd=RAIZ, check=True)
    generado = RAIZ / "dist" / "RevisorSSAA.exe"
    if DESTINO.exists():
        DESTINO.unlink()
    shutil.move(str(generado), DESTINO)
    shutil.rmtree(RAIZ / "dist", ignore_errors=True)
    shutil.rmtree(RAIZ / "build", ignore_errors=True)
    print("Generado %s (%.0f MB) en %.0f s" % (DESTINO.name, DESTINO.stat().st_size / 2**20,
                                              time.time() - inicio))


if __name__ == "__main__":
    main()
