# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates')],
    hiddenimports=['mido.backends.rtmidi', 'mido.backends.portmidi', 'mido.backends.pygame', 'flask', 'flask_cors', 'pythonosc', 'zeroconf', 'rtmidi', 'kivy', 'kivy.core', 'kivy.core.window', 'kivy.core.window.window_sdl2', 'kivy.core.audio', 'kivy.core.audio.audio_sdl2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='stagebridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='stagebridge.app',
    icon=None,
    bundle_identifier=None,
)
