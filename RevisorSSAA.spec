# -*- mode: python ; coding: utf-8 -*-
# No lanzar directamente: usar construir_exe.py (compila, deja "Revisor SSAA.exe" en la
# carpeta del proyecto y limpia). No incluye credenciales ni datos de clientes.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

MODULOS = ['config', 'curva_consumo', 'estilo', 'gemweb', 'graficos', 'informe',
           'ssaa_datos_esios', 'ssaa_motor', 'lectores_factura', 'lectores_factura.base',
           'lectores_factura.endesa', 'lectores_factura.naturgy']

datas = [('app_revision_ssaa.py', '.'), ('assets', 'assets'), ('.streamlit/config.toml', '.streamlit')]
# el script de Streamlit importa los modulos del proyecto desde su carpeta
datas += [(m + '.py', '.') for m in MODULOS if '.' not in m and m != 'lectores_factura']
datas += [('lectores_factura/*.py', 'lectores_factura')]
datas += collect_data_files('streamlit') + copy_metadata('streamlit')
datas += collect_data_files('altair') + collect_data_files('jsonschema_specifications')
for paquete in ('altair', 'pandas', 'pyarrow', 'openpyxl', 'requests', 'narwhals'):
    try:
        datas += copy_metadata(paquete)
    except Exception:
        pass

a = Analysis(
    ['lanzador.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=MODULOS + collect_submodules('streamlit') + ['xlrd', 'openpyxl', 'fitz',
                                                                 'requests', 'altair'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide6', 'PySide2', 'PyQt6', 'scipy', 'IPython', 'jupyter', 'notebook',
              'sphinx', 'dask', 'jedi', 'docutils', 'black', 'pytest', 'sqlalchemy', 'numba',
              'llvmlite', 'tensorflow', 'torch', 'sklearn', 'statsmodels', 'bokeh', 'panel',
              'holoviews', 'distributed', 'tables', 'h5py', 'nbformat', 'win32com', 'pythoncom',
              'botocore', 'boto3', 'sympy', 'matplotlib', 'tkinter', 'cv2', 'skimage',
              'astropy', 'xarray', 'seaborn', 'plotly', 'spyder', 'numexpr', 'bottleneck',
              'streamlit.testing', 'pypdf', 'pypdfium2', 'PIL.ImageQt'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RevisorSSAA',
    icon='assets/icono.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
)
