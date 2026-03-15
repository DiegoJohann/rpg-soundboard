from PyQt6 import QtWidgets, QtCore

class PlayerItemWidget(QtWidgets.QWidget):
    """
    Widget que representa uma faixa em reprodução com controles:
    - label (nome do arquivo)
    - pause/resume
    - stop (chama callback)
    - slider de volume
    The on_stop_callback will receive the widget instance so caller can
    map it to the corresponding uid/list item.
    """

    def __init__(self, name: str, player, on_stop_callback):
        super().__init__()
        self.player = player
        self.on_stop_callback = on_stop_callback

        # layout / spacing
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(6, 3, 6, 3)
        self.layout.setSpacing(6)

        # slightly smaller minimum height (compact but clickable)
        self.setMinimumHeight(32)

        self.name_label = QtWidgets.QLabel(name)
        self.name_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)

        self.pause_btn = QtWidgets.QPushButton("⏸")
        self.pause_btn.setFixedWidth(32)
        self.pause_btn.clicked.connect(self.toggle_pause)

        self.stop_btn = QtWidgets.QPushButton("⏹")
        self.stop_btn.setFixedWidth(32)
        self.stop_btn.clicked.connect(self.stop)

        self.vol_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 200)
        self.vol_slider.setFixedWidth(120)

        try:
            current_vol = self.player.audio_get_volume() or 80
        except Exception:
            current_vol = 80
        self.vol_slider.setValue(int(current_vol))
        self.vol_slider.valueChanged.connect(self.change_volume)

        self.vol_label = QtWidgets.QLabel(f"{self.vol_slider.value():>3}%")
        self.vol_label.setFixedWidth(40)
        self.vol_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        # compose
        self.layout.addWidget(self.name_label)
        self.layout.addWidget(self.pause_btn)
        self.layout.addWidget(self.stop_btn)
        self.layout.addWidget(self.vol_slider)
        self.layout.addWidget(self.vol_label)

        self.paused = False

    def toggle_pause(self):
        if not self.player:
            return
        try:
            self.player.pause()
            self.paused = not self.paused
            self.pause_btn.setText("▶" if self.paused else "⏸")
        except Exception:
            pass

    def stop(self):
        if not self.player:
            return
        try:
            self.player.stop()
        except Exception:
            pass
        # inform caller it should remove this widget's item and release resources
        try:
            self.on_stop_callback(self)
        except Exception:
            pass

    def change_volume(self, value: int):
        try:
            self.player.audio_set_volume(int(value))
        except Exception:
            pass
        self.vol_label.setText(f"{int(value):>3}%")

    def set_name(self, name: str):
        self.name_label.setText(name)
