# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import subprocess
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

root = Path(SPECPATH)
os.chdir(root)
tesseract_dir = Path(os.environ.get('TESSERACT_DIR', r'C:\Program Files\Tesseract-OCR'))
node_exe = Path(os.environ.get('NODE_EXE') or shutil.which('node') or 'vendor/node/node.exe')
for required in (tesseract_dir / 'tesseract.exe',
                 tesseract_dir / 'tessdata/eng.traineddata', node_exe):
    if not required.is_file():
        raise SystemExit(f'Missing native dependency: {required}. Set TESSERACT_DIR / NODE_EXE; see README.md.')
subprocess.run([str(tesseract_dir / 'tesseract.exe'), '--version'], check=True)
subprocess.run([str(node_exe), '--version'], check=True)

extra_data = [(str(tesseract_dir), 'tesseract'), (str(node_exe), 'node'),
              ('logo.ico', '.'), ('Autoclick.png', '.'), ('autoclick-icone.png', '.')]
hidden = ['pystray._win32', 'PIL.ImageTk', 'PIL.ImageGrab', 'psycopg2',
          'psycopg2.extras', 'pymysql', 'pytesseract', 'core.runtime_paths']
hidden += collect_submodules('i18n')
hidden += collect_submodules('cryptography')
for package in ('pystray', 'Pillow', 'python-i18n', 'psycopg2-binary',
                'PyMySQL', 'pytesseract', 'cryptography'):
    extra_data += copy_metadata(package)


a = Analysis(
    ['flow_builder_pro.py'],
    pathex=[],
    binaries=[],
    datas=[('locales', 'locales'), ('assets', 'assets')] + extra_data,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['scripts/runtime_hook.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoClick',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutoClick',
)
