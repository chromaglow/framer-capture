"""Entry point: DPI awareness -> logging/crash handler -> single instance -> app."""
from __future__ import annotations

import atexit
import logging
import logging.handlers
import os
import sys
import traceback

from . import APP_USER_MODEL_ID, __version__, win32

MUTEX_NAME = r"Local\Framer_SingleInstance_v1"
SERVER_NAME = "Framer_v1"

log = logging.getLogger("framer")


def setup_logging() -> None:
    from .settings import app_data_dir

    try:
        d = app_data_dir()
        d.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            d / "framer.log", maxBytes=1_000_000, backupCount=1, encoding="utf-8"
        )
    except OSError:
        handler = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if sys.stderr is not None and not getattr(sys, "frozen", False):
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)


def install_crash_handler() -> None:
    from .settings import app_data_dir

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log.critical("Unhandled exception:\n%s", text)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                box = QMessageBox()
                box.setIcon(QMessageBox.Icon.Critical)
                box.setWindowTitle("Framer ran into a problem")
                box.setText("Framer hit an unexpected error. Details were written to the log.")
                box.setDetailedText(text)
                open_btn = box.addButton("Open log folder", QMessageBox.ButtonRole.ActionRole)
                box.addButton("Continue", QMessageBox.ButtonRole.AcceptRole)
                box.exec()
                if box.clickedButton() is open_btn:
                    try:
                        os.startfile(str(app_data_dir()))  # type: ignore[attr-defined]
                    except OSError:
                        pass
        except Exception:
            pass

    sys.excepthook = hook


def _send_show_to_running_instance() -> bool:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtNetwork import QLocalSocket

    app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(1500):
        sock.write(b"show\n")
        sock.flush()
        sock.waitForBytesWritten(1000)
        sock.disconnectFromServer()
        return True
    del app
    return False


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    awareness = win32.set_process_dpi_awareness()
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    win32.set_app_user_model_id(APP_USER_MODEL_ID)
    setup_logging()
    install_crash_handler()
    log.info("Framer %s starting (DPI awareness: %s, frozen=%s)", __version__, awareness, bool(getattr(sys, "frozen", False)))

    if "--self-test" in argv:
        from .selftest import run

        return run(ci_mode="--ci" in argv)

    if not win32.acquire_single_instance_mutex(MUTEX_NAME):
        log.info("Another instance is running; asking it to show")
        _send_show_to_running_instance()
        return 0

    from PySide6.QtNetwork import QLocalServer
    from PySide6.QtWidgets import QApplication

    from . import theme
    from .app import FramerApp
    from .resources import app_icon
    from .settings import Settings

    app = QApplication(argv)
    app.setApplicationName("Framer")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Ezra")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(theme.STYLESHEET)
    app.setWindowIcon(app_icon())

    settings = Settings().load()
    framer = FramerApp(app, settings)

    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    server.listen(SERVER_NAME)

    def on_connection() -> None:
        conn = server.nextPendingConnection()
        if conn is None:
            return

        def read() -> None:
            data = bytes(conn.readAll()).strip()
            if b"show" in data:
                framer.show_setup()
            conn.disconnectFromServer()

        conn.readyRead.connect(read)

    server.newConnection.connect(on_connection)

    atexit.register(framer.hotkeys.unregister_all)
    framer.start()
    rc = app.exec()
    log.info("Framer exiting with %s", rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
