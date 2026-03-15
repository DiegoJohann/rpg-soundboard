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
    """
    Main window for the RPG Soundboard.
    """

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

        # masters: store original items (name, fullpath) for filtering
        self._trilhas_master = []  # list[tuple[str, str]]
        self._efeitos_master = []  # list[tuple[str, str]]

        # sound manager (lambda references default_vol_spin later, that's fine)
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

    # ---------------- UI ----------------
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

        # Trilhas group with search bar
        self.trilhas_group = QtWidgets.QGroupBox("Trilhas (background)")
        trilhas_layout = QtWidgets.QVBoxLayout(self.trilhas_group)

        self.trilhas_search = self._make_search_input("Buscar trilhas (Ctrl+F)...")
        self.trilhas_search.textChanged.connect(lambda txt: self._apply_filter("trilha", txt))
        trilhas_layout.addWidget(self.trilhas_search)

        self.trilhas_list = QtWidgets.QListWidget()
        self.trilhas_list.setSpacing(4)
        self.trilhas_list.setStyleSheet(self._list_stylesheet())
        self.trilhas_list.itemDoubleClicked.connect(lambda it: self.play_from_item(it, "trilha"))
        trilhas_layout.addWidget(self.trilhas_list)

        trilhas_refresh_btn = QtWidgets.QPushButton("Atualizar lista de Trilhas")
        trilhas_refresh_btn.clicked.connect(lambda: self.refresh_list("trilha"))
        trilhas_layout.addWidget(trilhas_refresh_btn)

        # Efeitos group with search bar
        self.efeitos_group = QtWidgets.QGroupBox("Efeitos (momentâneos)")
        efeitos_layout = QtWidgets.QVBoxLayout(self.efeitos_group)

        self.efeitos_search = self._make_search_input("Buscar efeitos (Ctrl+Shift+F)...")
        self.efeitos_search.textChanged.connect(lambda txt: self._apply_filter("efeito", txt))
        efeitos_layout.addWidget(self.efeitos_search)

        self.efeitos_list = QtWidgets.QListWidget()
        self.efeitos_list.setSpacing(4)
        self.efeitos_list.setStyleSheet(self._list_stylesheet())
        self.efeitos_list.itemDoubleClicked.connect(lambda it: self.play_from_item(it, "efeito"))
        efeitos_layout.addWidget(self.efeitos_list)

        efeitos_refresh_btn = QtWidgets.QPushButton("Atualizar lista de Efeitos")
        efeitos_refresh_btn.clicked.connect(lambda: self.refresh_list("efeito"))
        efeitos_layout.addWidget(efeitos_refresh_btn)

        lists_layout.addWidget(self.trilhas_group)
        lists_layout.addWidget(self.efeitos_group)

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

        self.trilhas_search.installEventFilter(self)
        self.efeitos_search.installEventFilter(self)

    def _make_search_input(self, placeholder: str) -> QtWidgets.QLineEdit:
        le = QtWidgets.QLineEdit()
        le.setPlaceholderText(placeholder)
        le.setClearButtonEnabled(True)
        le.setMaximumHeight(28)
        try:
            action = le.addAction(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView), QtWidgets.QLineEdit.ActionPosition.LeadingPosition)
            action.setToolTip("Busca")
        except Exception:
            pass
        return le

    def eventFilter(self, obj, event):
        # pressing Esc in search fields clears them (quick reset)
        if event.type() == QtCore.QEvent.Type.KeyPress:
            if isinstance(obj, QtWidgets.QLineEdit):
                key = event.key()
                if key == QtCore.Qt.Key.Key_Escape:
                    obj.clear()
                    return True
        return super().eventFilter(obj, event)

    # ----------------- persistence & file selection -----------------
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
            self.trilhas_search.setFocus()

    def choose_efeitos_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Selecionar pasta de Efeitos")
        if d:
            self.config["efeitos_dir"] = d
            self.efeitos_dir_label.setText(d)
            save_config(self.config)
            self.refresh_list("efeito")
            self.efeitos_search.setFocus()

    # ----------------- list population & filtering -----------------
    def refresh_list(self, list_type: str):
        """
        Populate the master list for `list_type` and apply current filter.
        We keep a master list of (display_name, full_path), so filtering is quick,
        and we don't repeatedly hit the filesystem while the user types.
        """
        master = []
        if list_type == "trilha":
            base = self.config.get("trilhas_dir") or ""
        else:
            base = self.config.get("efeitos_dir") or ""

        if base and os.path.isdir(base):
            files = sorted(os.listdir(base))
            for f in files:
                full = os.path.join(base, f)
                if os.path.isfile(full) and is_audio_file(full):
                    master.append((f, full))

        if list_type == "trilha":
            self._trilhas_master = master
            # update group title with count
            self.trilhas_group.setTitle(f"Trilhas (background) — {len(master)}")
            # apply current search query
            self._apply_filter("trilha", self.trilhas_search.text().strip())
        else:
            self._efeitos_master = master
            self.efeitos_group.setTitle(f"Efeitos (momentâneos) — {len(master)}")
            self._apply_filter("efeito", self.efeitos_search.text().strip())

    def _apply_filter(self, list_type: str, query: str):
        """Filter the corresponding QListWidget using the master's entries."""
        q = query.casefold() if query else ""
        if list_type == "trilha":
            master = self._trilhas_master
            widget = self.trilhas_list
        else:
            master = self._efeitos_master
            widget = self.efeitos_list

        widget.clear()
        count = 0
        for name, full in master:
            if not q or q in name.casefold():
                item = QtWidgets.QListWidgetItem(name)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, full)
                item.setSizeHint(QtCore.QSize(0, 28))
                widget.addItem(item)
                count += 1

        # Update group title with filtered count to give feedback
        if list_type == "trilha":
            self.trilhas_group.setTitle(f"Trilhas (background) — {count}")
        else:
            self.efeitos_group.setTitle(f"Efeitos (momentâneos) — {count}")

    # ----------------- playback / UI wiring -----------------
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
        uid = getattr(widget, "_uid", None)
        if not uid:
            for k, v in self._uid_map.items():
                if v["widget"] is widget:
                    uid = k
                    break
        if not uid:
            return
        entry = self._uid_map.pop(uid, None)
        if entry:
            try:
                row = self.playing_list_widget.row(entry["list_item"])
                self.playing_list_widget.takeItem(row)
            except Exception:
                pass
        try:
            self.sound_manager.stop(uid)
        except Exception:
            pass

    def stop_all(self):
        for uid, entry in list(self._uid_map.items()):
            try:
                row = self.playing_list_widget.row(entry["list_item"])
                self.playing_list_widget.takeItem(row)
            except Exception:
                pass
        self._uid_map.clear()
        try:
            self.sound_manager.stop_all()
        except Exception:
            pass

    # ----------------- keyboard shortcuts -----------------
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

        sc_trilhas_dir = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+T"), self)
        sc_trilhas_dir.activated.connect(self.choose_trilhas_dir)

        sc_efeitos_dir = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+E"), self)
        sc_efeitos_dir.activated.connect(self.choose_efeitos_dir)

        # UX navigation shortcuts for search focus
        sc_focus_trilhas_search = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self)
        sc_focus_trilhas_search.activated.connect(lambda: self.trilhas_search.setFocus())

        sc_focus_efeitos_search = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+F"), self)
        sc_focus_efeitos_search.activated.connect(lambda: self.efeitos_search.setFocus())

        for sc in (
            sc_enter, sc_space, sc_del, sc_refresh, sc_stopall,
            sc_trilhas_dir, sc_efeitos_dir,
            sc_focus_trilhas_search, sc_focus_efeitos_search
        ):
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
