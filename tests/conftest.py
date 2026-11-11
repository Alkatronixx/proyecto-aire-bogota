"""Prepara la raíz del repositorio para la colección de pruebas.
El ejecutable pytest de consola no siempre agrega el directorio de trabajo a sys.path.
Se registra la raíz antes de que los módulos de prueba importen el paquete app.
No carga datos ni ejecuta transformaciones durante la colección.
"""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ROOT_TEXTO = str(ROOT)
if ROOT_TEXTO not in sys.path:
    sys.path.insert(0, ROOT_TEXTO)
