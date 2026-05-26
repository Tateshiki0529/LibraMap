"""
libramap.main

LibraMap アプリケーションのエントリーポイント。
PySide6 アプリケーションを初期化してメインウィンドウを起動する。
"""
import sys

from PySide6.QtWidgets import QApplication

from libramap.ui.main_window import MainWindow


def main() -> None:
    """
    アプリケーションのメイン関数。

    PySide6 の QApplication を生成し、メインウィンドウを表示する。
    """
    app = QApplication(sys.argv)
    app.setApplicationName("LibraMap")
    app.setApplicationVersion("0.1.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
