from PyQt6 import QtWidgets, QtCore


class PlayerItemWidget(QtWidgets.QWidget):
    """
    Widget que representa uma faixa em reprodução com controles:
    - rótulo com o nome do arquivo
    - botão pausar/retomar
    - botão parar (invoca callback fornecida)
    - slider de volume (0..200%)

    Observação: o parâmetro `on_stop_callback` é chamado com a própria instância
    do widget quando o usuário solicita parada; isso permite ao chamador remover
    o item da UI e liberar recursos associados.
    """

    def __init__(self, name: str, player, on_stop_callback):
        """
        Inicializa o widget de controle de faixa.

        Args:
            name: texto a ser exibido como nome da faixa.
            player: objeto vlc.MediaPlayer (ou stub compatível) que controla a reprodução.
            on_stop_callback: função chamada quando o usuário pressiona 'stop';
                a função receberá esta instância como argumento.
        """
        super().__init__()
        self.player = player
        self.callback_parar = on_stop_callback

        # layout e espaçamento internos
        self.layout_principal = QtWidgets.QHBoxLayout(self)
        self.layout_principal.setContentsMargins(6, 3, 6, 3)
        self.layout_principal.setSpacing(6)

        # altura mínima para manter compactação mas clicável
        self.setMinimumHeight(32)

        # rótulo com o nome da faixa
        self.rotulo_nome = QtWidgets.QLabel(name)
        self.rotulo_nome.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)

        # botão pausar / retomar
        self.botao_pausa = QtWidgets.QPushButton("⏸")
        self.botao_pausa.setFixedWidth(32)
        self.botao_pausa.clicked.connect(self.toggle_pause)

        # botão parar
        self.botao_parar = QtWidgets.QPushButton("⏹")
        self.botao_parar.setFixedWidth(32)
        self.botao_parar.clicked.connect(self.stop)

        # slider de volume — permitimos até 200% para amplificação
        self.slider_volume = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_volume.setRange(0, 200)
        self.slider_volume.setFixedWidth(120)

        try:
            valor_atual = self.player.audio_get_volume() or 80
        except Exception:
            valor_atual = 80
        self.slider_volume.setValue(int(valor_atual))
        self.slider_volume.valueChanged.connect(self.change_volume)

        # rótulo que mostra o valor do volume
        self.rotulo_volume = QtWidgets.QLabel(f"{self.slider_volume.value():>3}%")
        self.rotulo_volume.setFixedWidth(40)
        self.rotulo_volume.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        # composição dos widgets no layout
        self.layout_principal.addWidget(self.rotulo_nome)
        self.layout_principal.addWidget(self.botao_pausa)
        self.layout_principal.addWidget(self.botao_parar)
        self.layout_principal.addWidget(self.slider_volume)
        self.layout_principal.addWidget(self.rotulo_volume)

        # estado interno
        self.pausado = False

    def toggle_pause(self):
        """
        Alterna o estado de pausa do player.
        Atualiza também o texto do botão para indicar o estado atual.
        """
        if not self.player:
            return
        try:
            self.player.pause()
            self.pausado = not self.pausado
            self.botao_pausa.setText("▶" if self.pausado else "⏸")
        except Exception:
            # falhas no player não devem quebrar a UI
            pass

    def stop(self):
        """
        Para a reprodução do player associado e notifica o callback externo
        para que a UI possa remover este widget e liberar recursos.
        """
        if not self.player:
            return
        try:
            self.player.stop()
        except Exception:
            pass
        try:
            self.callback_parar(self)
        except Exception:
            pass

    def change_volume(self, value: int):
        """
        Ajusta o volume do player para o valor fornecido (0..200).
        Atualiza o rótulo que exibe a porcentagem.
        """
        try:
            v = max(0, min(int(value), 200))
            self.player.audio_set_volume(v)
        except Exception:
            pass
        self.rotulo_volume.setText(f"{int(value):>3}%")

    def set_name(self, name: str):
        """Atualiza o texto do rótulo que mostra o nome da faixa."""
        self.rotulo_nome.setText(name)
