import os
from PyQt6 import QtWidgets, QtCore, QtGui

from .config import load_config, save_config
from .utils import is_audio_file
from .widgets import PlayerItemWidget
from .sound_manager import SoundManager

try:
    import vlc
except Exception:
    vlc = None

class SoundboardWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RPG Soundboard")
        self.resize(1200, 900)

        if vlc is None:
            QtWidgets.QMessageBox.critical(
                None,
                "Dependência ausente",
                "A biblioteca python-vlc não foi encontrada. Instale com:\n\npip install python-vlc\n\nAlém disso, instale o VLC/libVLC no seu sistema.",
            )
            # keep consistent with previous behavior: exit app
            import sys
            sys.exit(1)

        self.config = load_config()

        # maps: uid -> (list_item, widget)
        self._uid_map = {}

        # sound manager
        self.sound_manager = SoundManager(default_volume_getter=lambda: self.default_vol_spin.value())

        # build UI (calls methods that reference default_vol_spin)
        self._build_ui()
        self._setup_shortcuts()

        # initial refresh
        self.refresh_list("trilha")
        self.refresh_list("efeito")

        # cleanup timer (1s) - remove finished effects
        self.cleanup_timer = QtCore.QTimer()
        self.cleanup_timer.setInterval(1000)
        self.cleanup_timer.timeout.connect(self._cleanup_finished)
        self.cleanup_timer.start()

    def _list_stylesheet(self) -> str:
        return (
            "QListWidget { font-size: 10pt; }"
            "QListWidget::item { padding: 4px 6px; }"
        )

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top row: folder selectors + default volume
        top_row = QtWidgets.QHBoxLayout()
        layout.addLayout(top_row)

        self.trilhas_dir_label = QtWidgets.QLabel(self.config.get("trilhas_dir") or "Nenhuma pasta selecionada")
        self.efeitos_dir_label = QtWidgets.QLabel(self.config.get("efeitos_dir") or "Nenhuma pasta selecionada")

        trilhas_btn = QtWidgets.QPushButton("Escolher pasta de Trilhas")
        trilhas_btn.clicked.connect(self.choose_trilhas_dir)
        efeitos_btn = QtWidgets.QPushButton("Escolher pasta de Efeitos")
        efeitos_btn.clicked.connect(self.choose_efeitos_dir)

        top_row.addWidget(trilhas_btn)
        top_row.addWidget(self.trilhas_dir_label)
        top_row.addSpacing(20)
        top_row.addWidget(efeitos_btn)
        top_row.addWidget(self.efeitos_dir_label)
        top_row.addStretch()

        vol_label = QtWidgets.QLabel("Volume padrão:")
        self.default_vol_spin = QtWidgets.QSpinBox()
        self.default_vol_spin.setRange(0, 200)
        self.default_vol_spin.setValue(self.config.get("default_volume", 80))
        self.default_vol_spin.setSuffix("%")
        self.default_vol_spin.valueChanged.connect(self.save_settings)

        top_row.addWidget(vol_label)
        top_row.addWidget(self.default_vol_spin)

        # Middle: lists side-by-side (Trilhas / Efeitos)
        lists_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(lists_layout)

        trilhas_group = QtWidgets.QGroupBox("Trilhas (background)")
        trilhas_layout = QtWidgets.QVBoxLayout(trilhas_group)
        self.trilhas_list = QtWidgets.QListWidget()
        self.trilhas_list.setSpacing(4)
        self.trilhas_list.setStyleSheet(self._list_stylesheet())
        self.trilhas_list.itemDoubleClicked.connect(lambda it: self.play_from_item(it, "trilha"))
        trilhas_refresh_btn = QtWidgets.QPushButton("Atualizar lista de Trilhas")
        trilhas_refresh_btn.clicked.connect(lambda: self.refresh_list("trilha"))
        trilhas_layout.addWidget(self.trilhas_list)
        trilhas_layout.addWidget(trilhas_refresh_btn)

        efeitos_group = QtWidgets.QGroupBox("Efeitos (momentâneos)")
        efeitos_layout = QtWidgets.QVBoxLayout(efeitos_group)
        self.efeitos_list = QtWidgets.QListWidget()
        self.efeitos_list.setSpacing(4)
        self.efeitos_list.setStyleSheet(self._list_stylesheet())
        self.efeitos_list.itemDoubleClicked.connect(lambda it: self.play_from_item(it, "efeito"))
        efeitos_refresh_btn = QtWidgets.QPushButton("Atualizar lista de Efeitos")
        efeitos_refresh_btn.clicked.connect(lambda: self.refresh_list("efeito"))
        efeitos_layout.addWidget(self.efeitos_list)
        efeitos_layout.addWidget(efeitos_refresh_btn)

        lists_layout.addWidget(trilhas_group)
        lists_layout.addWidget(efeitos_group)

        # Bottom: Tocando agora
        playing_group = QtWidgets.QGroupBox("Tocando agora")
        playing_layout = QtWidgets.QVBoxLayout(playing_group)
        self.playing_list_widget = QtWidgets.QListWidget()
        self.playing_list_widget.setSpacing(4)
        self.playing_list_widget.setStyleSheet(self._list_stylesheet())
        playing_layout.addWidget(self.playing_list_widget)
        clear_all_btn = QtWidgets.QPushButton("Parar todas")
        clear_all_btn.clicked.connect(self.stop_all)
        playing_layout.addWidget(clear_all_btn)

        layout.addWidget(playing_group)

    # config persistence
    def save_settings(self):
        self.config["trilhas_dir"] = self.config.get("trilhas_dir", "")
        self.config["efeitos_dir"] = self.config.get("efeitos_dir", "")
        self.config["default_volume"] = int(self.default_vol_spin.value())
        save_config(self.config)

    def choose_trilhas_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Selecionar pasta de Trilhas")
        if d:
            self.config["trilhas_dir"] = d
            self.trilhas_dir_label.setText(d)
            save_config(self.config)
            self.refresh_list("trilha")

    def choose_efeitos_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Selecionar pasta de Efeitos")
        if d:
            self.config["efeitos_dir"] = d
            self.efeitos_dir_label.setText(d)
            save_config(self.config)
            self.refresh_list("efeito")

    def refresh_list(self, list_type: str):
        if list_type == "trilha":
            w = self.trilhas_list
            base = self.config.get("trilhas_dir") or ""
        else:
            w = self.efeitos_list
            base = self.config.get("efeitos_dir") or ""

        w.clear()
        if base and os.path.isdir(base):
            files = sorted(os.listdir(base))
            for f in files:
                full = os.path.join(base, f)
                if os.path.isfile(full) and is_audio_file(full):
                    item = QtWidgets.QListWidgetItem(f)
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, full)
                    item.setSizeHint(QtCore.QSize(0, 28))
                    w.addItem(item)

    def play_from_item(self, item: QtWidgets.QListWidgetItem, kind: str):
        path = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not path or not os.path.isfile(path):
            return
        try:
            uid, player = self.sound_manager.play_file(path, kind)
        except RuntimeError as e:
            QtWidgets.QMessageBox.warning(self, "Erro ao reproduzir", str(e))
            return

        display_name = f"{os.path.basename(path)}  [{kind}]"
        widget = PlayerItemWidget(display_name, player, on_stop_callback=self._on_widget_stop)
        # attach uid to widget so callback can find which uid it belongs to
        widget._uid = uid

        list_item = QtWidgets.QListWidgetItem()
        list_item.setSizeHint(QtCore.QSize(0, 44))
        self.playing_list_widget.addItem(list_item)
        self.playing_list_widget.setItemWidget(list_item, widget)

        # record mapping to remove later
        self._uid_map[uid] = {"list_item": list_item, "widget": widget}

    def _on_widget_stop(self, widget):
        # widget is the PlayerItemWidget instance that invoked stop()
        uid = getattr(widget, "_uid", None)
        if not uid:
            # fallback: try to find uid in map by identity
            for k, v in self._uid_map.items():
                if v["widget"] is widget:
                    uid = k
                    break
        if not uid:
            return
        # remove UI
        entry = self._uid_map.pop(uid, None)
        if entry:
            try:
                row = self.playing_list_widget.row(entry["list_item"])
                self.playing_list_widget.takeItem(row)
            except Exception:
                pass
        # stop player resources
        try:
            self.sound_manager.stop(uid)
        except Exception:
            pass

    def stop_all(self):
        # remove UI items
        for uid, entry in list(self._uid_map.items()):
            try:
                row = self.playing_list_widget.row(entry["list_item"])
                self.playing_list_widget.takeItem(row)
            except Exception:
                pass
        self._uid_map.clear()
        # stop players
        try:
            self.sound_manager.stop_all()
        except Exception:
            pass

    # keyboard shortcuts
    def _setup_shortcuts(self):
        sc_enter = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Return), self)
        sc_enter.activated.connect(self._play_selected)

        sc_space = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Space), self)
        sc_space.activated.connect(self._toggle_pause_selected)

        sc_del = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete), self)
        sc_del.activated.connect(self._stop_selected)

        sc_refresh = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self)
        sc_refresh.activated.connect(lambda: (self.refresh_list("trilha"), self.refresh_list("efeito")))

        sc_stopall = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+K"), self)
        sc_stopall.activated.connect(self.stop_all)

        sc_trilhas = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+T"), self)
        sc_trilhas.activated.connect(self.choose_trilhas_dir)

        sc_efeitos = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+E"), self)
        sc_efeitos.activated.connect(self.choose_efeitos_dir)

        for sc in (sc_enter, sc_space, sc_del, sc_refresh, sc_stopall, sc_trilhas, sc_efeitos):
            sc.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)

    def _play_selected(self):
        # prioritize list that has focus
        current = None
        kind = None
        if self.trilhas_list.hasFocus():
            current = self.trilhas_list.currentItem()
            kind = "trilha"
        elif self.efeitos_list.hasFocus():
            current = self.efeitos_list.currentItem()
            kind = "efeito"
        else:
            current = self.trilhas_list.currentItem() or self.efeitos_list.currentItem()
            kind = "trilha" if self.trilhas_list.currentItem() else "efeito"
        if current:
            self.play_from_item(current, kind)

    def _toggle_pause_selected(self):
        item = self.playing_list_widget.currentItem()
        if not item:
            return
        widget = self.playing_list_widget.itemWidget(item)
        if hasattr(widget, "toggle_pause"):
            try:
                widget.toggle_pause()
            except Exception:
                pass

    def _stop_selected(self):
        item = self.playing_list_widget.currentItem()
        if not item:
            return
        widget = self.playing_list_widget.itemWidget(item)
        if hasattr(widget, "stop"):
            try:
                widget.stop()
            except Exception:
                pass

    def _cleanup_finished(self):
        # ask sound_manager to cleanup; it returns removed uids
        removed = self.sound_manager.cleanup_finished()
        for uid in removed:
            entry = self._uid_map.pop(uid, None)
            if not entry:
                continue
            try:
                row = self.playing_list_widget.row(entry["list_item"])
                self.playing_list_widget.takeItem(row)
            except Exception:
                pass
