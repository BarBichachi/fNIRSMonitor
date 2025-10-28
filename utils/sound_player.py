from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect
import os
import config

class SoundPlayer:
    # Handles loading and playing audible alert sounds.
    def __init__(self):
        # Initializes the SoundPlayer and loads the sound effects.
        self.effects = {}
        self._load_sounds()

    def _load_sounds(self):
        # Creates and loads the sound files for the alerts from paths in the config.
        self._load_effect('alert', config.ALERT_SOUND_PATH)
        self._load_effect('nominal', config.NOMINAL_SOUND_PATH)

    def _load_effect(self, name, path):
        # Helper function to load a single sound effect.
        self.effects[name] = QSoundEffect()
        if os.path.exists(path):
            self.effects[name].setSource(QUrl.fromLocalFile(path))
            self.effects[name].setVolume(0.8)
        else:
            print(f"Warning: Sound file not found at '{path}'. Sound will be silent.")

    def play(self, sound_name):
        # Plays the sound corresponding to the given name ('alert' or 'nominal').
        if sound_name in self.effects and self.effects[sound_name].isLoaded():
            self.effects[sound_name].play()
