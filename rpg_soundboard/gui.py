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


def _list_stylesheet() -> str:
    """Retorna a stylesheet usada nas listas para melhor legibilidade."""
    return (
        "QListWidget { font-size: 10pt; }"
        "QListWidget::item { padding: 4px 6px; }"
    )


class SoundboardWindow(QtWidgets.QMainWindow):
    """
    Janela principal do RPG Soundboard.
    Contém listas de trilhas e efeitos, área 'Tocando agora', busca nas listas
    e integração com o SoundManager responsável pela reprodução.
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
            import sys
            sys.exit(1)

        # carregar configuração persistida
        self.config = load_config()

        # mapa de itens tocando: uid -> {"list_item": ..., "widget": ...}
        self._map_tocando = {}

        # listas mestres (nome, caminho) usadas para filtragem/ busca rápida
        self._trilhas_mestre = []  # list[tuple[str, str]]
        self._efeitos_mestre = []  # list[tuple[str, str]]

        # gerenciador de áudio (a lambda referencia o spin que será criado em _build_ui)
        self.sound_manager = SoundManager(default_volume_getter=lambda: self.spin_volume_padrao.value())

        # montar interface e atalhos
        self._build_ui()
        self._setup_shortcuts()

        # preencher listas iniciais
        self.refresh_list("trilha")
        self.refresh_list("efeito")

        # timer de limpeza periódica (remove efeitos finalizados)
        self.timer_limpeza = QtCore.QTimer()
        self.timer_limpeza.setInterval(1000)
        self.timer_limpeza.timeout.connect(self._cleanup_finished)
        self.timer_limpeza.start()

    # ---------------- UI ----------------
    def _build_ui(self):
        """
        Constrói toda a interface gráfica:
        - topo com seleção de pastas e controle de volume padrão;
        - colunas com Trilhas e Efeitos (cada uma com caixa de busca);
        - área 'Tocando agora' com controles por faixa.
        Também instala filtros de evento para permitir limpar buscas com ESC.
        """
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Linha superior: seleção de pastas e volume padrão
        linha_topo = QtWidgets.QHBoxLayout()
        layout.addLayout(linha_topo)

        self.label_pasta_trilhas = QtWidgets.QLabel(self.config.get("trilhas_dir") or "Nenhuma pasta selecionada")
        self.label_pasta_efeitos = QtWidgets.QLabel(self.config.get("efeitos_dir") or "Nenhuma pasta selecionada")

        botao_trilhas = QtWidgets.QPushButton("Escolher pasta de Trilhas")
        botao_trilhas.clicked.connect(self.choose_trilhas_dir)
        botao_efeitos = QtWidgets.QPushButton("Escolher pasta de Efeitos")
        botao_efeitos.clicked.connect(self.choose_efeitos_dir)

        linha_topo.addWidget(botao_trilhas)
        linha_topo.addWidget(self.label_pasta_trilhas)
        linha_topo.addSpacing(20)
        linha_topo.addWidget(botao_efeitos)
        linha_topo.addWidget(self.label_pasta_efeitos)
        linha_topo.addStretch()

        rotulo_volume = QtWidgets.QLabel("Volume padrão:")
        self.spin_volume_padrao = QtWidgets.QSpinBox()
        self.spin_volume_padrao.setRange(0, 200)
        self.spin_volume_padrao.setValue(self.config.get("default_volume", 80))
        self.spin_volume_padrao.setSuffix("%")
        self.spin_volume_padrao.valueChanged.connect(self.save_settings)

        linha_topo.addWidget(rotulo_volume)
        linha_topo.addWidget(self.spin_volume_padrao)

        # Área central: listas lado a lado
        layout_listas = QtWidgets.QHBoxLayout()
        layout.addLayout(layout_listas)

        # Grupo Trilhas com campo de busca
        self.grupo_trilhas = QtWidgets.QGroupBox("Trilhas (background)")
        layout_trilhas = QtWidgets.QVBoxLayout(self.grupo_trilhas)

        self.busca_trilhas = self._criar_campo_busca("Buscar trilhas (Ctrl+F)...")
        self.busca_trilhas.textChanged.connect(lambda txt: self._apply_filter("trilha", txt))
        layout_trilhas.addWidget(self.busca_trilhas)

        self.lista_trilhas = QtWidgets.QListWidget()
        self.lista_trilhas.setSpacing(4)
        self.lista_trilhas.setStyleSheet(_list_stylesheet())
        self.lista_trilhas.itemDoubleClicked.connect(lambda it: self.play_from_item(it, "trilha"))
        layout_trilhas.addWidget(self.lista_trilhas)

        botao_atualizar_trilhas = QtWidgets.QPushButton("Atualizar lista de Trilhas")
        botao_atualizar_trilhas.clicked.connect(lambda: self.refresh_list("trilha"))
        layout_trilhas.addWidget(botao_atualizar_trilhas)

        # Grupo Efeitos com campo de busca
        self.grupo_efeitos = QtWidgets.QGroupBox("Efeitos (momentâneos)")
        layout_efeitos = QtWidgets.QVBoxLayout(self.grupo_efeitos)

        self.busca_efeitos = self._criar_campo_busca("Buscar efeitos (Ctrl+Shift+F)...")
        self.busca_efeitos.textChanged.connect(lambda txt: self._apply_filter("efeito", txt))
        layout_efeitos.addWidget(self.busca_efeitos)

        self.lista_efeitos = QtWidgets.QListWidget()
        self.lista_efeitos.setSpacing(4)
        self.lista_efeitos.setStyleSheet(_list_stylesheet())
        self.lista_efeitos.itemDoubleClicked.connect(lambda it: self.play_from_item(it, "efeito"))
        layout_efeitos.addWidget(self.lista_efeitos)

        botao_atualizar_efeitos = QtWidgets.QPushButton("Atualizar lista de Efeitos")
        botao_atualizar_efeitos.clicked.connect(lambda: self.refresh_list("efeito"))
        layout_efeitos.addWidget(botao_atualizar_efeitos)

        layout_listas.addWidget(self.grupo_trilhas)
        layout_listas.addWidget(self.grupo_efeitos)

        # Painel de One-Shots / Quick triggers
        grupo_quick = QtWidgets.QGroupBox("Painel Rápido")
        layout_quick = QtWidgets.QHBoxLayout(grupo_quick)
        self.quick_area = QtWidgets.QWidget()
        self.quick_layout = QtWidgets.QHBoxLayout(self.quick_area)
        layout_quick.addWidget(self.quick_area)
        self._reload_quick_panel()
        layout.addWidget(grupo_quick)

        # Área inferior: Tocando agora
        grupo_tocando = QtWidgets.QGroupBox("Tocando agora")
        layout_tocando = QtWidgets.QVBoxLayout(grupo_tocando)
        self.lista_tocando = QtWidgets.QListWidget()
        self.lista_tocando.setSpacing(4)
        self.lista_tocando.setStyleSheet(_list_stylesheet())
        layout_tocando.addWidget(self.lista_tocando)
        botao_parar_tudo = QtWidgets.QPushButton("Parar todas")
        botao_parar_tudo.clicked.connect(self.stop_all)
        layout_tocando.addWidget(botao_parar_tudo)

        layout.addWidget(grupo_tocando)

        # permitir limpar busca com ESC
        self.busca_trilhas.installEventFilter(self)
        self.busca_efeitos.installEventFilter(self)

        # context menu para listas (favoritar)
        self.lista_trilhas.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista_trilhas.customContextMenuRequested.connect(lambda pos: self._open_context_menu(self.lista_trilhas, pos))
        self.lista_efeitos.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista_efeitos.customContextMenuRequested.connect(lambda pos: self._open_context_menu(self.lista_efeitos, pos))

    def _criar_campo_busca(self, placeholder: str) -> QtWidgets.QLineEdit:
        """
        Cria e estiliza um QLineEdit para busca com comportamento UX apropriado:
        - placeholder
        - botão de limpar
        - ícone sutil (quando disponível)
        - altura limitada para não aumentar visualmente a lista
        """
        campo = QtWidgets.QLineEdit()
        campo.setPlaceholderText(placeholder)
        campo.setClearButtonEnabled(True)
        campo.setMaximumHeight(28)
        try:
            action = campo.addAction(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView), QtWidgets.QLineEdit.ActionPosition.LeadingPosition)
            action.setToolTip("Buscar")
        except Exception:
            pass
        return campo

    def eventFilter(self, obj, event):
        """
        Intercepta eventos para permitir:
        - ESC em campos de busca para limpá-los rapidamente.
        """
        if event.type() == QtCore.QEvent.Type.KeyPress:
            if isinstance(obj, QtWidgets.QLineEdit):
                key = event.key()
                if key == QtCore.Qt.Key.Key_Escape:
                    obj.clear()
                    return True
        return super().eventFilter(obj, event)

    # ----------------- persistência e seleção de pastas -----------------
    def save_settings(self):
        """
        Persiste no arquivo de configuração as pastas selecionadas e o volume padrão.
        Chamado quando o usuário altera o spin de volume ou ao escolher pastas.
        """
        self.config["trilhas_dir"] = self.config.get("trilhas_dir", "")
        self.config["efeitos_dir"] = self.config.get("efeitos_dir", "")
        self.config["default_volume"] = int(self.spin_volume_padrao.value())
        save_config(self.config)

    def choose_trilhas_dir(self):
        """
        Abre diálogo para o usuário escolher a pasta de trilhas.
        Atualiza a UI, salva a configuração e re-foca o campo de busca.
        """
        pasta = QtWidgets.QFileDialog.getExistingDirectory(self, "Selecionar pasta de Trilhas")
        if pasta:
            self.config["trilhas_dir"] = pasta
            self.label_pasta_trilhas.setText(pasta)
            save_config(self.config)
            self.refresh_list("trilha")
            self.busca_trilhas.setFocus()

    def choose_efeitos_dir(self):
        """
        Abre diálogo para o usuário escolher a pasta de efeitos.
        Atualiza a UI, salva a configuração e re-foca o campo de busca.
        """
        pasta = QtWidgets.QFileDialog.getExistingDirectory(self, "Selecionar pasta de Efeitos")
        if pasta:
            self.config["efeitos_dir"] = pasta
            self.label_pasta_efeitos.setText(pasta)
            save_config(self.config)
            self.refresh_list("efeito")
            self.busca_efeitos.setFocus()

    # ----------------- população e filtragem das listas -----------------
    def refresh_list(self, tipo_lista: str):
        """
        Recarrega a lista 'trilha' ou 'efeito' lendo o diretório configurado
        e atualiza a lista mestre. Em seguida aplica o filtro atual (se houver).
        Mantemos a lista mestre em memória para filtrar rapidamente sem tocar no FS.
        """
        mestre = []
        if tipo_lista == "trilha":
            base = self.config.get("trilhas_dir") or ""
        else:
            base = self.config.get("efeitos_dir") or ""

        if base and os.path.isdir(base):
            arquivos = sorted(os.listdir(base))
            for nome in arquivos:
                caminho = os.path.join(base, nome)
                if os.path.isfile(caminho) and is_audio_file(caminho):
                    mestre.append((nome, caminho))

        if tipo_lista == "trilha":
            self._trilhas_mestre = mestre
            self.grupo_trilhas.setTitle(f"Trilhas (background) — {len(mestre)}")
            self._apply_filter("trilha", self.busca_trilhas.text().strip())
        else:
            self._efeitos_mestre = mestre
            self.grupo_efeitos.setTitle(f"Efeitos (momentâneos) — {len(mestre)}")
            self._apply_filter("efeito", self.busca_efeitos.text().strip())

    def _apply_filter(self, tipo_lista: str, consulta: str):
        """
        Filtra a lista exibida com base na 'consulta' (case-insensitive).
        Atualiza o título do grupo com o número de resultados.
        """
        q = consulta.casefold() if consulta else ""
        if tipo_lista == "trilha":
            mestre = self._trilhas_mestre
            widget = self.lista_trilhas
        else:
            mestre = self._efeitos_mestre
            widget = self.lista_efeitos

        widget.clear()
        cont = 0
        favs = set(self.config.get("favorites", []))
        for nome, caminho in mestre:
            if not q or q in nome.casefold():
                display = nome
                if caminho in favs:
                    display = "★ " + display
                item = QtWidgets.QListWidgetItem(display)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, caminho)
                item.setSizeHint(QtCore.QSize(0, 28))
                widget.addItem(item)
                cont += 1

        if tipo_lista == "trilha":
            self.grupo_trilhas.setTitle(f"Trilhas (background) — {cont}")
        else:
            self.grupo_efeitos.setTitle(f"Efeitos (momentâneos) — {cont}")

    def _open_context_menu(self, widget: QtWidgets.QListWidget, pos):
        item = widget.itemAt(pos)
        if not item:
            return

        caminho = item.data(QtCore.Qt.ItemDataRole.UserRole)
        menu = QtWidgets.QMenu()
        fav = "Desmarcar favorito" if caminho in self.config.get("favorites", []) else "Marcar favorito"
        act_fav = menu.addAction(fav)
        act_play = menu.addAction("Tocar")
        act_show = menu.addAction("Mostrar no FS")
        a = menu.exec(widget.mapToGlobal(pos))

        if a == act_fav:
            self._toggle_favorite(caminho)
        elif a == act_play:
            # descobrir tipo pela pasta
            self.play_from_item(item, "trilha" if widget is self.lista_trilhas else "efeito")
        elif a == act_show:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(caminho))

    def _toggle_favorite(self, caminho: str):
        favs = set(self.config.get("favorites", []))

        if caminho in favs:
            favs.remove(caminho)
            self.statusBar().showMessage("Removido dos favoritos", 2500)
        else:
            if len(favs) >= 5:
                self.statusBar().showMessage("Limite de 5 favoritos atingido.", 3000)
                return

            favs.add(caminho)
            self.statusBar().showMessage("Adicionado aos favoritos", 2500)

        self.config["favorites"] = list(favs)
        save_config(self.config)

        self.refresh_list("trilha")
        self.refresh_list("efeito")
        self._reload_quick_panel()

    # ----------------- reprodução e ligação UI -----------------
    def play_from_item(self, item: QtWidgets.QListWidgetItem, tipo: str):
        """
        Inicia a reprodução do arquivo associado ao item selecionado.
        Cria um PlayerItemWidget na lista 'Tocando agora' e registra o uid.
        """
        caminho = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not caminho or not os.path.isfile(caminho):
            self.statusBar().showMessage("Arquivo inválido.", 3000)
            return

        try:
            uid, player = self.sound_manager.play_file(caminho, tipo)
        except RuntimeError as e:
            QtWidgets.QMessageBox.warning(self, "Erro ao reproduzir", str(e))
            return

        nome_exibicao = f"{os.path.basename(caminho)}  [{tipo}]"
        self._add_playing_widget(uid, player, nome_exibicao)

    def _add_playing_widget(self, uid, player, nome_exibicao: str):
        """
        Adiciona à lista 'Tocando agora' o widget associado a um player ativo
        e registra sua referência no mapa interno.
        """
        widget_faixa = PlayerItemWidget(
            nome_exibicao,
            player,
            on_stop_callback=self._on_widget_stop,
        )
        widget_faixa._uid = uid

        item_lista = QtWidgets.QListWidgetItem()
        item_lista.setSizeHint(QtCore.QSize(0, 44))
        self.lista_tocando.addItem(item_lista)
        self.lista_tocando.setItemWidget(item_lista, widget_faixa)

        self._map_tocando[uid] = {"list_item": item_lista, "widget": widget_faixa}
        self.statusBar().showMessage(f"Tocando: {nome_exibicao}", 2500)

    def _on_widget_stop(self, widget):
        """
        Callback chamado quando um PlayerItemWidget solicita stop.
        Remove o item da UI e libera os recursos no SoundManager.
        """
        uid = getattr(widget, "_uid", None)
        if not uid:
            for k, v in self._map_tocando.items():
                if v["widget"] is widget:
                    uid = k
                    break
        if not uid:
            return
        entrada = self._map_tocando.pop(uid, None)
        if entrada:
            try:
                linha = self.lista_tocando.row(entrada["list_item"])
                self.lista_tocando.takeItem(linha)
            except Exception:
                pass
        try:
            self.sound_manager.stop(uid)
        except Exception:
            pass

    def stop_all(self):
        """
        Para todas as faixas ativas e limpa a lista 'Tocando agora'.
        """
        for uid, entrada in list(self._map_tocando.items()):
            try:
                linha = self.lista_tocando.row(entrada["list_item"])
                self.lista_tocando.takeItem(linha)
            except Exception:
                pass
        self._map_tocando.clear()
        try:
            self.sound_manager.stop_all()
        except Exception:
            pass

    # ----------------- atalhos de teclado -----------------
    def _setup_shortcuts(self):
        """
        Registra atalhos de teclado globais para melhorar fluxo em sessão:
        - Enter, Space, Delete, Ctrl+R, Ctrl+K, Ctrl+T, Ctrl+E
        - Ctrl+F foca busca de trilhas; Ctrl+Shift+F foca busca de efeitos
        """
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

        sc_focus_busca_trilhas = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self)
        sc_focus_busca_trilhas.activated.connect(lambda: self.busca_trilhas.setFocus())

        sc_focus_busca_efeitos = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+F"), self)
        sc_focus_busca_efeitos.activated.connect(lambda: self.busca_efeitos.setFocus())

        for sc in (
            sc_enter, sc_space, sc_del, sc_refresh, sc_stopall,
            sc_trilhas_dir, sc_efeitos_dir,
            sc_focus_busca_trilhas, sc_focus_busca_efeitos
        ):
            sc.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)

    def _play_path_via_hotkey(self, path: str):
        # tenta tocar diretamente (se arquivo não existir -> mensagem)
        if not os.path.isfile(path):
            self.statusBar().showMessage("Hotkey: arquivo não encontrado.", 3000)
            return

        # decidir tipo: se estiver na pasta trilhas -> trilha, else efeito
        tipo = "trilha" if path.startswith(self.config.get("trilhas_dir", "")) else "efeito"

        # criar um item temporário para reaproveitar lógica
        nome_exibicao = f"{os.path.basename(path)}  [{tipo}]"
        try:
            uid, player = self.sound_manager.play_file(path, tipo)
        except RuntimeError as e:
            self.statusBar().showMessage(f"Erro ao tocar hotkey: {e}", 3000)
            return

        self._add_playing_widget(uid, player, nome_exibicao)
        self.statusBar().showMessage(f"Tocando (hotkey): {os.path.basename(path)}", 2000)

    def _play_selected(self):
        """
        Toca o item atualmente selecionado, priorizando a lista com foco.
        """
        if self.lista_trilhas.hasFocus():
            atual = self.lista_trilhas.currentItem()
            tipo = "trilha"
        elif self.lista_efeitos.hasFocus():
            atual = self.lista_efeitos.currentItem()
            tipo = "efeito"
        else:
            atual = self.lista_trilhas.currentItem() or self.lista_efeitos.currentItem()
            tipo = "trilha" if self.lista_trilhas.currentItem() else "efeito"
        if atual:
            self.play_from_item(atual, tipo)

    def _toggle_pause_selected(self):
        """
        Pausa/retoma a faixa selecionada na lista 'Tocando agora'.
        """
        item = self.lista_tocando.currentItem()
        if not item:
            return
        widget = self.lista_tocando.itemWidget(item)
        if hasattr(widget, "toggle_pause"):
            try:
                widget.toggle_pause()
            except Exception:
                pass

    def _stop_selected(self):
        """
        Para a faixa selecionada na lista 'Tocando agora' (invoca o stop do widget).
        """
        item = self.lista_tocando.currentItem()
        if not item:
            return
        widget = self.lista_tocando.itemWidget(item)
        if hasattr(widget, "stop"):
            try:
                widget.stop()
            except Exception:
                pass

    def _cleanup_finished(self):
        """
        Pergunta ao SoundManager pelas uids removidas (efeitos finalizados)
        e atualiza a UI removendo os itens correspondentes.
        """
        removidos = self.sound_manager.cleanup_finished()
        for uid in removidos:
            entrada = self._map_tocando.pop(uid, None)
            if not entrada:
                continue
            try:
                linha = self.lista_tocando.row(entrada["list_item"])
                self.lista_tocando.takeItem(linha)
            except Exception:
                pass

    # quick panel: mostra até 6 favoritos como botões
    def _reload_quick_panel(self):
        # limpar
        for i in reversed(range(self.quick_layout.count())):
            w = self.quick_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        favs = list(self.config.get("favorites", []))

        # criar botões + hotkeys
        for i, caminho in enumerate(favs[:5]):
            seq = f"Ctrl+{i + 1}"

            shortcut = QtGui.QShortcut(QtGui.QKeySequence(seq), self)
            shortcut.activated.connect(lambda p=caminho: self._play_path_via_hotkey(p))

            b = QtWidgets.QPushButton(f"{i + 1} - {os.path.basename(caminho)}")
            b.setToolTip(f"{seq} → {caminho}")

            b.clicked.connect(lambda _, path=caminho: self._play_path_via_hotkey(path))

            self.quick_layout.addWidget(b)

        # se vazio, instrução
        if not favs:
            lab = QtWidgets.QLabel("Marque favoritos (clique direito) para aparecer aqui.")
            self.quick_layout.addWidget(lab)
