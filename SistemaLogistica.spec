# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('vendor', 'vendor'),
        ('firma_cartas', 'firma_cartas'),
        ('test_files', 'test_files')
    ],
    hiddenimports=['pandas._libs.tslibs.timedeltas', 'ttkbootstrap.themes'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='SistemaLogistica',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False, # True para depurar, False para la versión final
    disable_windowed_traceback=False, # Mantenlo en False para ver errores
    icon=None, # Aquí puedes poner la ruta a un archivo .ico
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SistemaLogistica',
)
