import os
import json
from mido import MidiFile

class FileUtils:
    @staticmethod
    def load_syx(file_path):
        with open(file_path, 'rb') as f:
            return list(f.read())

    @staticmethod
    def save_syx(file_path, data):
        with open(file_path, 'wb') as f:
            f.write(bytes(data))

    @staticmethod
    def load_mid(file_path):
        return MidiFile(file_path)

    @staticmethod
    def save_mid(file_path, midi_file):
        midi_file.save(file_path)

    @staticmethod
    def load_command_json(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
