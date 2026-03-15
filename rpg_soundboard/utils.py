import pathlib


def is_audio_file(path: str):
    ext = pathlib.Path(path).suffix.lower()
    return ext in [".mp3", ".ogg", ".wav", ".flac", ".aac", ".m4a", ".opus"]
