# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: one-file, windowed Framer.exe with icon, version info and PerMonitorV2 manifest."""
from pathlib import Path

ROOT = Path(SPECPATH)

# Qt modules Framer does not use; excluding them keeps the exe small and the build robust.
QT_EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.QtWebSockets", "PySide6.QtWebView",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtSpatialAudio",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuickControls2", "PySide6.QtQuick3D",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSerialBus", "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtStateMachine",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtXml", "PySide6.QtSvg", "PySide6.QtSvgWidgets", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtPrintSupport", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools", "PySide6.QtConcurrent", "PySide6.QtDBus",
    "PySide6.QtHttpServer", "PySide6.QtTextToSpeech", "PySide6.QtAsyncio", "PySide6.QtExampleIcons",
    "tkinter", "unittest", "pydoc", "doctest", "xmlrpc", "matplotlib", "scipy", "IPython",
]

a = Analysis(
    [str(ROOT / "framer" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "framer" / "assets" / "framer.ico"), "framer/assets"),
        (str(ROOT / "framer" / "assets" / "click.wav"), "framer/assets"),
    ],
    hiddenimports=["PySide6.QtNetwork"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=QT_EXCLUDES,
    noarchive=False,
    optimize=0,
)

# Drop heavyweight Qt binaries and plugins that slipped through (translations, QML, unneeded platforms).
def _keep(entry):
    name = entry[0].replace("\\", "/").lower()
    drop_fragments = (
        "qt6webengine", "qt6quick", "qt6qml", "qt6pdf", "qt63d", "qt6charts", "qt6multimedia", "qt6designer",
        "qt6sql", "qt6test", "qt6svg", "qt6opengl", "qt6printsupport", "qt6xml", "qt6help", "qt6virtualkeyboard",
        "qt6shadertools", "qt6labs", "qt6location", "qt6positioning", "qt6sensors", "qt6serial", "qt6bluetooth",
        "qt6nfc", "qt6remoteobjects", "qt6scxml", "qt6statemachine", "qt6texttospeech", "qt6spatialaudio",
        "qt6httpserver", "qt6websockets", "qt6webchannel", "qt6webview", "qt6graphs", "qt6datavisualization",
        "qt6concurrent", "qt6dbus", "qt6uitools",
        "pyside6/translations/", "pyside6/qml/", "pyside6/plugins/sqldrivers", "pyside6/plugins/multimedia",
        "pyside6/plugins/tls", "pyside6/plugins/networkinformation", "pyside6/plugins/printsupport",
        "pyside6/plugins/qmltooling", "pyside6/plugins/scenegraph", "pyside6/plugins/position", "pyside6/plugins/sensors",
        "pyside6/plugins/renderers", "pyside6/plugins/sceneparsers", "pyside6/plugins/geometryloaders",
        "pyside6/plugins/texttospeech", "pyside6/plugins/designer", "pyside6/plugins/assetimporters",
        "pyside6/plugins/generic", "pyside6/plugins/iconengines", "pyside6/plugins/imageformats/qsvg",
        "pyside6/plugins/imageformats/qpdf", "pyside6/plugins/platforms/qoffscreen", "pyside6/plugins/platforms/qminimal",
        "pyside6/plugins/platforms/qdirect2d", "pyside6/plugins/platformthemes", "pyside6/plugins/platforminputcontexts",
        "opengl32sw", "d3dcompiler", "libegl", "libgles", "qt6opengl",
        "pyside6/lupdate", "pyside6/lrelease", "pyside6/assistant", "pyside6/designer", "pyside6/linguist",
        "pyside6/qmlls", "pyside6/qmllint", "pyside6/qmlformat", "pyside6/qsb", "pyside6/balsam", "pyside6/svgtoqml",
        "pyside6/rcc", "pyside6/uic", "pyside6/qmlimportscanner", "pyside6/qmltyperegistrar", "pyside6/qmlcachegen",
        "pyside6/glue/", "pyside6/typesystems/", "pyside6/include/", "pyside6/scripts/", "pyside6/support/",
        "pyside6/examples/", "pyside6/qtexampleicons",
    )
    return not any(f in name for f in drop_fragments)

a.binaries = TOC([e for e in a.binaries if _keep(e)])
a.datas = TOC([e for e in a.datas if _keep(e)])

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Framer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "framer" / "assets" / "framer.ico"),
    version=str(ROOT / "version_info.txt"),
    manifest=str(ROOT / "framer.manifest"),
    uac_admin=False,
    uac_uiaccess=False,
)
