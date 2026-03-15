import uuid
from typing import Dict

try:
    import vlc
except Exception:
    vlc = None


class SoundManager:
    """
    Gerencia o ciclo de vida dos players de áudio baseados em VLC.

    Mantém um registro interno das reproduções ativas no formato:
        uid -> {player, path, kind}

    Onde:
        uid   : identificador único da reprodução
        player: instância vlc.MediaPlayer
        path  : caminho do arquivo de áudio
        kind  : tipo ("trilha" ou "efeito")
    """

    def __init__(self, default_volume_getter):
        """
        Inicializa o gerenciador de áudio.

        Args:
            default_volume_getter:
                Função que retorna o volume padrão atual definido na UI.
                Esse valor é aplicado automaticamente quando um áudio inicia.
        """
        self.default_volume_getter = default_volume_getter
        self.players_ativos: Dict[str, Dict] = {}

        if vlc is None:
            self.instancia = None
        else:
            self.instancia = vlc.Instance()

    def play_file(self, path: str, tipo: str):
        """
        Inicia a reprodução de um arquivo de áudio.

        Args:
            path: caminho do arquivo.
            tipo: "trilha" (loop infinito) ou "efeito" (toca uma vez).

        Returns:
            Tuple (uid, player) onde:
                uid    : identificador único da reprodução
                player : instância do player VLC criada

        Raises:
            RuntimeError se a biblioteca VLC não estiver disponível
            ou se a reprodução não puder ser iniciada.
        """
        if vlc is None:
            raise RuntimeError("python-vlc (libVLC) não encontrado")

        instancia = self.instancia

        if tipo == "trilha":
            media = instancia.media_new(path, "input-repeat=-1")
        else:
            media = instancia.media_new(path)

        player = instancia.media_player_new()
        player.set_media(media)

        try:
            player.audio_set_volume(int(self.default_volume_getter()))
        except Exception:
            pass

        try:
            player.play()
        except Exception:
            try:
                player.play()
            except Exception as e:
                raise RuntimeError(f"Não foi possível reproduzir: {e}")

        uid = str(uuid.uuid4())
        self.players_ativos[uid] = {"player": player, "path": path, "tipo": tipo}

        return uid, player

    def stop(self, uid: str):
        """
        Interrompe e libera recursos de uma reprodução específica.

        Args:
            uid: identificador da reprodução a ser encerrada.
        """
        dados = self.players_ativos.pop(uid, None)
        if not dados:
            return

        try:
            dados["player"].stop()
        except Exception:
            pass

        try:
            dados["player"].release()
        except Exception:
            pass

    def stop_all(self):
        """
        Interrompe todas as reproduções ativas e limpa o registro interno.
        """
        for uid in list(self.players_ativos.keys()):
            self.stop(uid)

    def cleanup_finished(self):
        """
        Remove automaticamente efeitos sonoros que já terminaram.

        Trilhas (loops) não são removidas automaticamente.

        Returns:
            Lista de UIDs removidos, para que a interface possa
            atualizar a lista "Tocando agora".
        """
        if vlc is None:
            return []

        remover = []

        for uid, dados in list(self.players_ativos.items()):
            if dados["tipo"] == "trilha":
                continue

            try:
                estado = dados["player"].get_state()
            except Exception:
                estado = None

            if estado in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
                remover.append(uid)

        for uid in remover:
            self.stop(uid)

        return remover
