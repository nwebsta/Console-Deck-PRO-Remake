"""Voicemod-Modul für Console Deck Pro."""

from app.plugin_api import Param

from .client import VoicemodClient

RANDOM_MODES = [("AllVoices", "Alle Stimmen"), ("FavoriteVoices", "Favoriten"), ("CustomVoices", "Eigene Stimmen")]
LISTS = [("all", "Alle Stimmen"), ("favorites", "Nur Favoriten")]


def register(api):
    client = VoicemodClient(api.log, api.set_status)

    api.register_settings(
        [Param("client_key", "Client-Key", "password",
               help="Den Key bekommst du kostenlos im Voicemod Developer Portal "
                    "(https://control-api.voicemod.net). Voicemod muss laufen.")],
        on_change=lambda s: client.set_key(s.get("client_key", "")),
    )
    client.set_key(api.get_setting("client_key", ""))
    client.start()
    api.on_unload(client.stop)

    def voice_choices():
        return [(v["id"], ("★ " if v["favorite"] else "") + v["name"]) for v in client.voices]

    def sound_choices():
        return [(s["id"], s["name"]) for s in client.sounds]

    def voice_name(vid):
        return next((v["name"] for v in client.voices if v["id"] == vid), vid)

    def sound_name(sid):
        return next((s["name"].split(" › ")[-1] for s in client.sounds if s["id"] == sid), sid)

    # ------------------------------------------------------------------ Stimmen
    api.register_action(
        "load_voice", "Stimme laden",
        lambda m, ctx: client.send("loadVoice", {"voiceID": m.get("voice")}),
        [Param("voice", "Stimme", "choice", choices=voice_choices,
               help="Liste leer? Voicemod starten und mit ⟳ aktualisieren.")],
        summary=lambda m: f"Stimme: {voice_name(m.get('voice', ''))}",
    )
    api.register_action(
        "next_voice", "Nächste Stimme",
        lambda m, ctx: client.cycle_voice(1, m.get("list") == "favorites"),
        [Param("list", "Durchschalten", "choice", default="favorites", choices=LISTS)],
    )
    api.register_action(
        "prev_voice", "Vorherige Stimme",
        lambda m, ctx: client.cycle_voice(-1, m.get("list") == "favorites"),
        [Param("list", "Durchschalten", "choice", default="favorites", choices=LISTS)],
    )
    api.register_action(
        "random_voice", "Zufällige Stimme",
        lambda m, ctx: client.send("selectRandomVoice", {"mode": m.get("mode", "AllVoices")}),
        [Param("mode", "Aus", "choice", default="AllVoices", choices=RANDOM_MODES)],
    )

    # ------------------------------------------------------------------ Schalter
    api.register_action("toggle_voice_changer", "Voice Changer an/aus",
                        lambda m, ctx: client.send("toggleVoiceChanger"))
    api.register_action("toggle_hear_myself", "Mich selbst hören an/aus",
                        lambda m, ctx: client.send("toggleHearMyself"))
    api.register_action("toggle_background", "Hintergrundeffekte an/aus",
                        lambda m, ctx: client.send("toggleBackground"))
    api.register_action("toggle_mute_mic", "Mikrofon stumm an/aus",
                        lambda m, ctx: client.send("toggleMuteMic"))

    # ------------------------------------------------------------------ Soundboard
    api.register_action(
        "play_sound", "Soundboard: Sound abspielen",
        lambda m, ctx: client.send("playMeme", {"FileName": m.get("sound"), "IsKeyDown": True}),
        [Param("sound", "Sound", "choice", choices=sound_choices,
               help="Liste leer? Voicemod starten und mit ⟳ aktualisieren.")],
        summary=lambda m: f"Sound: {sound_name(m.get('sound', ''))}",
    )
    api.register_action("stop_sounds", "Soundboard: Alle Sounds stoppen",
                        lambda m, ctx: client.send("stopAllMemeSounds"))
    api.register_action("refresh", "Stimmen & Sounds neu laden",
                        lambda m, ctx: client.refresh_lists())
