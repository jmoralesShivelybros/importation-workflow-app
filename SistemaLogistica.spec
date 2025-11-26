# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('firma_cartas', 'firma_cartas'),
        ('vendor', 'vendor'),
        ('config.json', '.')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SistemaLogistica',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # Desactiva la compresión UPX para reducir falsos positivos.
    console=False,      # False para aplicaciones con GUI (--windowed).
    onefile=False,      # CAMBIO CLAVE: Genera una carpeta en lugar de un solo .exe.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,          # También desactivamos UPX en la fase de recolección.
    upx_exclude=[],
    name='SistemaLogistica',
)