from PySide6.QtCore import QThread, Signal
import time
import socket
import sys
import queue
from dialogs import Dialogs
from file_utils import FileUtils

class MIDIReceiveWorker(QThread):
    log = Signal(str)
    # Signals for different MIDI message types
    sysex_received = Signal(list)
    note_on_received = Signal(object)
    note_off_received = Signal(object)
    control_change_received = Signal(object)
    other_message_received = Signal(object)

    def __init__(self, midi_handler):
        super().__init__()
        self.midi_handler = midi_handler
        self.running = True

    def run(self):
        inport = self.midi_handler.inport
        if inport is None:
            self.log.emit("No MIDI input port open.")
            return
        try:
            for msg in inport:
                if not self.running:
                    break
                if msg.type == 'sysex':
                    self.sysex_received.emit(list(msg.data))
                elif msg.type == 'note_on':
                    self.note_on_received.emit(msg)
                elif msg.type == 'note_off':
                    self.note_off_received.emit(msg)
                elif msg.type == 'control_change':
                    self.control_change_received.emit(msg)
                else:
                    self.other_message_received.emit(msg)
        except Exception as e:
            self.log.emit(f"MIDI receive error: {e}")

    def stop(self):
        self.running = False
        self.wait()

class LogWorker(QThread):
    log = Signal(str)
    def __init__(self):
        super().__init__()
        self.messages = []
        self.running = True
    def run(self):
        while self.running:
            if self.messages:
                msg = self.messages.pop(0)
                self.log.emit(msg)
            self.msleep(100)
    def add_message(self, msg):
        self.messages.append(msg)
    def stop(self):
        self.running = False
        self.wait()

class MidiSendWorker(QThread):
    log = Signal(str)
    finished = Signal()
    def __init__(self, midi_outport, midi_file):
        super().__init__()
        self.midi_outport = midi_outport
        self.midi_file = midi_file
        self._stop = False
    def run(self):
        start_time = time.time()
        for msg in self.midi_file.play():
            if self._stop:
                self.log.emit("MIDI sending stopped by user.")
                break
            # Use the global MIDIHandler send_sysex if available
            if hasattr(self.midi_outport, 'send_sysex'):
                self.midi_outport.send_sysex(msg.bytes())
            else:
                self.midi_outport.send(msg)
        elapsed = time.time() - start_time
        self.log.emit(f"MIDI file sent in {elapsed:.2f} seconds.")
        self.finished.emit()
    def stop(self):
        self._stop = True

class SyslogWorker(QThread):
    syslog_message = Signal(str)
    log = Signal(str)
    def __init__(self, host='0.0.0.0', port=8514):
        super().__init__()
        self.host = host
        self.port = port
        self.running = True
        self.start_time = None
    def run(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                server.bind((self.host, self.port))
            except OSError as e:
                return self.log.emit(f"Syslog error: {e}")
            server.settimeout(0.5)
            self.log.emit(f"Syslog server listening on {socket.gethostbyname(socket.gethostname())}:{self.port}")
            while self.running:
                try:
                    data, address = server.recvfrom(1024)
                    self.handle_message(data)
                except socket.timeout:
                    continue
                except Exception as e:
                    self.log.emit(f"Syslog error: {e}")
            server.close()
            self.log.emit("Syslog server stopped.")
        except Exception as e:
            Dialogs.show_error(None, "Syslog Error", str(e))
            self.log.emit(f"Syslog error: {e}")
    def handle_message(self, data):
        message = data[2:].decode('utf-8', errors='replace').strip()
        if "Time exceeded (0)" in message:
            return
        if self.start_time is None:
            self.start_time = time.time()
            relative_time = "0:00:00.000"
        else:
            elapsed_time = time.time() - self.start_time
            hours = int(elapsed_time // 3600)
            minutes = int((elapsed_time % 3600) // 60)
            seconds = int(elapsed_time % 60)
            milliseconds = int((elapsed_time % 1) * 1000)
            relative_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        self.syslog_message.emit(f"{relative_time} {message}")
    def stop(self):
        self.running = False
        self.wait()

class FileLoadWorker(QThread):
    loaded = Signal(object, str)
    error = Signal(str)
    def __init__(self, file_path, file_type):
        super().__init__()
        self.file_path = file_path
        self.file_type = file_type  # 'mid' or 'syx'
    def run(self):
        try:
            if self.file_type == 'mid':
                midi = FileUtils.load_mid(self.file_path)
                self.loaded.emit(midi, self.file_path)
            elif self.file_type == 'syx':
                data = FileUtils.load_syx(self.file_path)
                self.loaded.emit(data, self.file_path)
            else:
                self.error.emit(f"Unknown file type: {self.file_type}")
        except Exception as e:
            self.error.emit(str(e))

class FileSaveWorker(QThread):
    saved = Signal(str)
    error = Signal(str)
    def __init__(self, file_path, file_type, data):
        super().__init__()
        self.file_path = file_path
        self.file_type = file_type  # 'mid' or 'syx'
        self.data = data
    def run(self):
        try:
            if self.file_type == 'mid':
                FileUtils.save_mid(self.file_path, self.data)
                self.saved.emit(self.file_path)
            elif self.file_type == 'syx':
                FileUtils.save_syx(self.file_path, self.data)
                self.saved.emit(self.file_path)
            else:
                self.error.emit(f"Unknown file type: {self.file_type}")
        except Exception as e:
            self.error.emit(str(e))

class MidiMessageSendWorker(QThread):
    log = Signal(str)
    def __init__(self, midi_outport):
        super().__init__()
        self.midi_outport = midi_outport
        self.msg_queue = queue.Queue()
        self.running = True
    def run(self):
        while self.running:
            try:
                msg = self.msg_queue.get(timeout=0.1)
                if msg is None:
                    break
                # Use the global MIDIHandler send_sysex if available
                if hasattr(self.midi_outport, 'send_sysex'):
                    self.midi_outport.send_sysex(msg.bytes())
                else:
                    self.midi_outport.send(msg)
            except queue.Empty:
                continue
    def send(self, msg):
        self.msg_queue.put(msg)
    def stop(self):
        self.running = False
        self.msg_queue.put(None)
        self.wait()

class FirewallCheckWorker(QThread):
    result = Signal(bool, str, list, set, set, bool)  # has_rule, current_profile, rule_profiles, enabled_profiles, disabled_profiles, has_block
    def run(self):
        from windows_firewall_checker import WindowsFirewallChecker
        has_rule, current_profile, rule_profiles, enabled_profiles, disabled_profiles, has_block = WindowsFirewallChecker.check_firewall_rule(verbose=True)
        self.result.emit(has_rule, current_profile, rule_profiles, enabled_profiles, disabled_profiles, has_block)
