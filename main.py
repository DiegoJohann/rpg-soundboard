#!/usr/bin/env python3
import sys
from PyQt6 import QtWidgets
from rpg_soundboard.gui import SoundboardWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = SoundboardWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
