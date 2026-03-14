import uuid
from typing import Dict

try:
    import vlc
except Exception:
    vlc = None

class SoundManager:
    """
    Lifecycle for vlc.MediaPlayer instances.
    Keeps an internal registry: uid -> {player, path, kind}
    """

    def __init__(self, default_volume_getter):
        # default_volume_getter: callable that returns current default volume (0-100)
        self.default_volume_getter = default_volume_getter
        self.active_players: Dict[str, Dict] = {}

    def play_file(self, path: str, kind: str):
        if vlc is None:
            raise RuntimeError("python-vlc (libVLC) não encontrado")

        instance = vlc.Instance()

        if kind == "trilha":
            media = instance.media_new(path, "input-repeat=-1")
        else:
            media = instance.media_new(path)

        player = instance.media_player_new()
        player.set_media(media)

        try:
            player.audio_set_volume(int(self.default_volume_getter()))
        except Exception:
            pass

        # try to start (call twice as original attempted)
        try:
            player.play()
        except Exception:
            try:
                player.play()
            except Exception as e:
                raise RuntimeError(f"Não foi possível reproduzir: {e}")

        uid = str(uuid.uuid4())
        self.active_players[uid] = {"player": player, "path": path, "kind": kind}
        return uid, player

    def stop(self, uid: str):
        data = self.active_players.pop(uid, None)
        if not data:
            return
        try:
            data["player"].stop()
        except Exception:
            pass
        try:
            data["player"].release()
        except Exception:
            pass

    def stop_all(self):
        for uid in list(self.active_players.keys()):
            self.stop(uid)

    def cleanup_finished(self):
        """
        Remove ended players (only non-looping ones).
        Returns the list of uids that were removed so caller can update UI.
        """
        if vlc is None:
            return []

        to_remove = []
        for uid, data in list(self.active_players.items()):
            if data["kind"] == "trilha":
                continue
            try:
                state = data["player"].get_state()
            except Exception:
                state = None
            if state in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
                to_remove.append(uid)

        for uid in to_remove:
            # reuse stop() to cleanup
            self.stop(uid)

        return to_remove
