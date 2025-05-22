import mido
from mido import MidiFile, Message
from workers import MidiMessageSendWorker
import socket
from PySide6.QtCore import Signal, QObject

class MIDIHandler(QObject):
    UDP_PORT_NAME = 'UDP Socket (127.0.0.1:50007)'
    UDP_MENU_LABEL = 'UDP Socket (127.0.0.1:50007)'
    UDP_HOST = '127.0.0.1'
    UDP_PORT = 50007

    log_message = Signal(str)

    def __init__(self):
        super().__init__()
        self.inport = None
        self.outport = None
        self._midi_send_worker = None
        self._midi_file_worker = None
        self._input_callbacks = {}
        self.udp_output_active = False
        self.udp_input_active = False
        self.udp_sock_out = None
        self.udp_sock_in = None
        self.forward_callback = None
        self._current_input_port_name = None
        self._current_output_port_name = None

    def list_input_ports(self):
        print("[MIDI LOG] list_input_ports called")
        ports = mido.get_input_names()
        ports.append(self.UDP_PORT_NAME)
        return ports

    def list_output_ports(self):
        print("[MIDI LOG] list_output_ports called")
        ports = mido.get_output_names()
        ports.append(self.UDP_PORT_NAME)
        return ports

    def open_input(self, port_name):
        print("[MIDI LOG] open_input called")
        if self.inport:
            self.inport.close()
            self.inport = None
        if self.udp_sock_in:
            self.udp_sock_in.close()
            self.udp_sock_in = None
            self.udp_input_active = False
        if port_name in (self.UDP_PORT_NAME, self.UDP_MENU_LABEL):
            self.udp_sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock_in.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_sock_in.bind((self.UDP_HOST, self.UDP_PORT))
            self.udp_input_active = True
            self._current_input_port_name = port_name
            # Start a thread to poll UDP input and call self.forward_any
            import threading
            def udp_poll():
                while self.udp_input_active:
                    try:
                        data, _ = self.udp_sock_in.recvfrom(1024)
                        if data:
                            self.forward_any(data)
                    except Exception:
                        break
            self._udp_thread = threading.Thread(target=udp_poll, daemon=True)
            self._udp_thread.start()
        elif port_name and isinstance(port_name, str):
            self.inport = mido.open_input(port_name, callback=self.forward_any)
            self.udp_input_active = False
            self._current_input_port_name = port_name
        else:
            # No port to open
            self.inport = None
            self.udp_input_active = False
            self._current_input_port_name = None

    def forward_any(self, msg):
        # Forward any incoming MIDI data (raw bytes or mido.Message) to the main window
        if hasattr(self, 'forward_callback') and self.forward_callback:
            self.forward_callback(msg)

    def set_forward_callback(self, callback):
        self.forward_callback = callback

    def open_output(self, port_name):
        print("[MIDI LOG] open_output called")
        print(f"[DEBUG] open_output: port_name={port_name!r}")
        if self.outport:
            self.close_output_worker()
            self.outport.close()
            self.outport = None
        if self.udp_sock_out:
            self.udp_sock_out.close()
            self.udp_sock_out = None
            self.udp_output_active = False
        # Normalize UDP port names
        udp_labels = (self.UDP_PORT_NAME, self.UDP_MENU_LABEL, 'UDP Socket (127.0.0.1:50007)', 'UDP MIDI (127.0.0.1:50007)')
        if port_name in udp_labels:
            print(f"[DEBUG] open_output: Detected UDP output selection.")
            self.udp_sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_output_active = True
            self.outport = None
            self._midi_send_worker = None
            self._current_output_port_name = port_name
        elif port_name and isinstance(port_name, str):
            print(f"[DEBUG] open_output: Detected real MIDI output selection.")
            self.outport = mido.open_output(port_name)
            self.udp_output_active = False
            self._midi_send_worker = MidiMessageSendWorker(self.outport)
            self._midi_send_worker.start()
            self._current_output_port_name = port_name
        else:
            self.outport = None
            self.udp_output_active = False
            self._current_output_port_name = None

    def close_output_worker(self):
        print("[MIDI LOG] close_output_worker called")
        if self._midi_send_worker:
            self._midi_send_worker.stop()
            self._midi_send_worker = None

    def close(self):
        print("[MIDI LOG] close called")
        if self.inport:
            self.inport.close()
            self.inport = None
        if self.udp_sock_in:
            self.udp_sock_in.close()
            self.udp_sock_in = None
            self.udp_input_active = False
        if self.outport:
            self.close_output_worker()
            self.outport.close()
            self.outport = None
        if self.udp_sock_out:
            self.udp_sock_out.close()
            self.udp_sock_out = None
            self.udp_output_active = False

    def send_sysex(self, data):
        self.log_message.emit(f"[MIDI LOG] send_sysex called: {data}")
        # Remove 0xF0 and 0xF7 if present
        if data and data[0] == 0xF0:
            data = data[1:]
        if data and data[-1] == 0xF7:
            data = data[:-1]
        # Check for out-of-range bytes
        if any((b < 0 or b > 127) for b in data):
            print(f"[MIDI LOG] Skipping SysEx: bytes out of range 0..127: {' '.join(f'{b:02X}' for b in data)}")
            return
        data_wrapped = [0xF0] + data + [0xF7]
        midi_bytes = bytes(data_wrapped)
        print(f"[MIDI LOG] Sending... {' '.join(f'{b:02X}' for b in data_wrapped)}")
        if self.udp_output_active and self.udp_sock_out:
            try:
                print(f"[DEBUG] UDP sendto: {list(midi_bytes)} to {(self.UDP_HOST, self.UDP_PORT)}")
                sent = self.udp_sock_out.sendto(midi_bytes, (self.UDP_HOST, self.UDP_PORT))
                print(f"[DEBUG] UDP sent {sent} bytes")
            except Exception as e:
                print(f"[ERROR] UDP sendto failed: {e}")
        elif self.outport and self._midi_send_worker:
            # Route all outport sends through send_mido_message for consistent debug
            msg = Message('sysex', data=data)
            self.send_mido_message(msg)

    def register_input_callback(self, msg_type, callback):
        """Register a callback for a MIDI message type (e.g., 'sysex', 'note_on')."""
        self._input_callbacks[msg_type] = callback

    def unregister_input_callback(self, msg_type):
        if msg_type in self._input_callbacks:
            del self._input_callbacks[msg_type]

    def handle_incoming_message(self, msg):
        cb = self._input_callbacks.get(msg.type)
        if cb:
            if msg.type == 'sysex':
                cb(list(msg.data))
            else:
                cb(msg)
        elif self._input_callbacks.get('other'):
            self._input_callbacks['other'](msg)

    def receive_sysex(self, callback):
        print("[MIDI LOG] receive_sysex called (deprecated, use register_input_callback)")
        self.register_input_callback('sysex', callback)

    def send_custom_midi_command(self, cmd, values):
        self.log_message.emit(f"[MIDI LOG] send_custom_midi_command: cmd={cmd.get('name', cmd)} values={values}")
        print("[MIDI LOG] send_custom_midi_command called")
        if not self.outport and not hasattr(self, 'main_window'):
            return
        status = cmd.get("status_byte", 0)
        params = list(values)
        dx7_names = [
            "DX7 Bulk Dump Request (Single Voice)",
            "DX7 Bulk Dump Request (32 Voices)",
            "DX7 Parameter Change",
            "DX7 Function Parameter Change",
            "DX7 Bulk Data (Single Voice)",
            "DX7 Bulk Data (32 Voices)"
        ]
        # Log what will be sent
        print(f"[MIDI LOG] send_custom_midi_command: cmd={cmd.get('name', cmd)} values={values}")
        if status == 0xF0 and cmd.get("name") in dx7_names:
            name = cmd.get("name")
            data = [0x43]
            if name == "DX7 Bulk Dump Request (Single Voice)":
                device, voice = params
                data += [0x10 | (device & 0x0F), 0x09, 0x20, voice]
            elif name == "DX7 Bulk Dump Request (32 Voices)":
                device = params[0]
                data += [0x10 | (device & 0x0F), 0x09, 0x00, 0x00]
            elif name == "DX7 Parameter Change":
                device, param, value = params
                data += [0x10 | (device & 0x0F), 0x01, param, value]
            elif name == "DX7 Function Parameter Change":
                device, func, value = params
                data += [0x10 | (device & 0x0F), 0x03, func, value]
            elif name == "DX7 Bulk Data (Single Voice)":
                device = params[0]
                voice_data = []
                if len(params) > 1 and isinstance(params[1], str):
                    voice_data = [int(x.strip()) for x in params[1].split(',') if x.strip()]
                data += [0x10 | (device & 0x0F), 0x00, 0x00] + voice_data
            elif name == "DX7 Bulk Data (32 Voices)":
                device = params[0]
                voice_data = []
                if len(params) > 1 and isinstance(params[1], str):
                    voice_data = [int(x.strip()) for x in params[1].split(',') if x.strip()]
                data += [0x10 | (device & 0x0F), 0x00, 0x09] + voice_data
            sysex_bytes = [0xF0] + data + [0xF7]
            print(f"[MIDI LOG] Sending DX7 SysEx: {' '.join(f'{b:02X}' for b in sysex_bytes)}")
            msg = Message('sysex', data=sysex_bytes[1:-1])
            self._midi_send_worker.send(msg)
            return
        elif status == 0xF0:
            data = [status] + params
            if data[0] == 0xF0:
                data = data[1:]
            if data and data[-1] == 0xF7:
                data = data[:-1]
            sysex_bytes = [0xF0] + data + [0xF7]
            print(f"[MIDI LOG] Sending generic SysEx: {' '.join(f'{b:02X}' for b in sysex_bytes)}")
            msg = Message('sysex', data=sysex_bytes[1:-1])
            self._midi_send_worker.send(msg)
            return
        else:
            if cmd["parameters"] and cmd["parameters"][0]["name"].lower() == "channel":
                channel = params.pop(0)
                status = (status & 0xF0) | ((channel - 1) & 0x0F)
            data = [status] + params
            print(f"[MIDI LOG] Sending MIDI: {' '.join(f'{b:02X}' for b in data)}")
            msg = Message.from_bytes(data)
            self._midi_send_worker.send(msg)
            return

    def get_command_hex(self, cmd, values):
        self.log_message.emit(f"[MIDI LOG] get_command_hex called: cmd={cmd.get('name', cmd)} values={values}")
        print("[MIDI LOG] get_command_hex called")
        # If a template is present, use it for SysEx construction
        template = cmd.get("template")
        if template:
            # Build a dict of parameter names to values
            param_map = {}
            for i, param in enumerate(cmd.get("parameters", [])):
                # Use lowercase and underscores for template keys
                key = param["name"].lower().replace(" ", "_")
                param_map[key] = values[i]
            # Special handling for nibbles (e.g., 1{device} means 0x10 | (device & 0x0F))
            import re
            def repl(m):
                prefix = m.group(1)
                key = m.group(2)
                if prefix and key in param_map:
                    # Interpret prefix as hex, bitwise OR with param
                    return f'{(int(prefix, 16) << 4) | (int(param_map[key]) & 0x0F):02X}'
                elif key in param_map:
                    return f'{int(param_map[key]):02X}'
                return m.group(0)
            # Match patterns like 2{device_number} or {device_number}
            hex_str = re.sub(r'([0-9A-Fa-f])\{([a-zA-Z0-9_]+)\}', repl, template)
            hex_str = re.sub(r'\{([a-zA-Z0-9_]+)\}', lambda m: f'{int(param_map[m.group(1)]):02X}' if m.group(1) in param_map else m.group(0), hex_str)
            # Remove spaces, split, and convert to bytes
            bytes_list = [int(b, 16) for b in hex_str.strip().split()]
            return ' '.join(f'{b:02X}' for b in bytes_list)
        status = cmd.get("status_byte", 0)
        params = list(values)
        dx7_names = [
            "DX7 Bulk Dump Request (Single Voice)",
            "DX7 Bulk Dump Request (32 Voices)",
            "DX7 Parameter Change",
            "DX7 Function Parameter Change",
            "DX7 Bulk Data (Single Voice)",
            "DX7 Bulk Data (32 Voices)"
        ]
        if status == 0xF0 and cmd.get("name") in dx7_names:
            name = cmd.get("name")
            data = [0x43]
            if name == "DX7 Bulk Dump Request (Single Voice)":
                device, voice = params
                data += [0x10 | (device & 0x0F), 0x09, 0x20, voice]
            elif name == "DX7 Bulk Dump Request (32 Voices)":
                device = params[0]
                data += [0x10 | (device & 0x0F), 0x09, 0x00, 0x00]
            elif name == "DX7 Parameter Change":
                device, param, value = params
                data += [0x10 | (device & 0x0F), 0x01, param, value]
            elif name == "DX7 Function Parameter Change":
                device, func, value = params
                data += [0x10 | (device & 0x0F), 0x03, func, value]
            elif name == "DX7 Bulk Data (Single Voice)":
                device = params[0]
                voice_data = []
                if len(params) > 1 and isinstance(params[1], str):
                    voice_data = [int(x.strip()) for x in params[1].split(',') if x.strip()]
                data += [0x10 | (device & 0x0F), 0x00, 0x00] + voice_data
            elif name == "DX7 Bulk Data (32 Voices)":
                device = params[0]
                voice_data = []
                if len(params) > 1 and isinstance(params[1], str):
                    voice_data = [int(x.strip()) for x in params[1].split(',') if x.strip()]
                data += [0x10 | (device & 0x0F), 0x00, 0x09] + voice_data
            sysex_bytes = [0xF0] + data + [0xF7]
            return ' '.join(f'{b:02X}' for b in sysex_bytes)
        elif status == 0xF0:
            data = [status] + params
            if data[0] == 0xF0:
                data = data[1:]
            if data and data[-1] == 0xF7:
                data = data[:-1]
            sysex_bytes = [0xF0] + data + [0xF7]
            return ' '.join(f'{b:02X}' for b in sysex_bytes)
        else:
            if cmd["parameters"] and cmd["parameters"][0]["name"].lower() == "channel":
                channel = params.pop(0)
                status = (status & 0xF0) | ((channel - 1) & 0x0F)
            data = [status] + params
            return ' '.join(f'{b:02X}' for b in data)

    def send_cc(self, channel, control, value):
        self.log_message.emit(f"[MIDI LOG] Sending CC: channel={channel+1} control={control} value={value}")
        msg_bytes = [0xB0 | (channel & 0x0F), control, value]
        midi_bytes = bytes(msg_bytes)
        print(f"[MIDI LOG] Sending... {' '.join(f'{b:02X}' for b in msg_bytes)}")
        if self.udp_output_active and self.udp_sock_out:
            try:
                print(f"[DEBUG] UDP sendto: {list(midi_bytes)} to {(self.UDP_HOST, self.UDP_PORT)}")
                sent = self.udp_sock_out.sendto(midi_bytes, (self.UDP_HOST, self.UDP_PORT))
                print(f"[DEBUG] UDP sent {sent} bytes")
            except Exception as e:
                print(f"[ERROR] UDP sendto failed: {e}")
        elif self.outport:
            # Route all outport sends through send_mido_message for consistent debug
            msg = mido.Message('control_change', channel=channel, control=control, value=value)
            self.send_mido_message(msg)

    def send_mido_message(self, msg):
        try:
            print(f"[MIDI LOG] send_mido_message called: {msg}")
            print(f"[DEBUG] send_mido_message: udp_output_active={self.udp_output_active}, udp_sock_out={self.udp_sock_out}, outport={self.outport}")
            assert hasattr(msg, 'bytes'), f"send_mido_message: msg must be a mido.Message, got {type(msg)}"
            midi_bytes = msg.bytes()
            # Fix: If msg.bytes() returns a list, convert to bytes
            if isinstance(midi_bytes, list):
                print(f"[DEBUG] msg.bytes() returned a list, converting to bytes: {midi_bytes}")
                midi_bytes = bytes(midi_bytes)
            assert isinstance(midi_bytes, (bytes, bytearray)), f"msg.bytes() must return bytes, got {type(midi_bytes)}"
            print(f"[MIDI LOG] Sending... {' '.join(f'{b:02X}' for b in midi_bytes)}")
            print("[DEBUG] About to check UDP send block condition")
            if self.udp_output_active and self.udp_sock_out:
                print("[DEBUG] Entering UDP send block in send_mido_message")
                try:
                    print("[DEBUG] About to send UDP packet")
                    print(f"[DEBUG] UDP sendto: {list(midi_bytes)} to {(self.UDP_HOST, self.UDP_PORT)}")
                    sent = self.udp_sock_out.sendto(midi_bytes, (self.UDP_HOST, self.UDP_PORT))
                    print(f"[DEBUG] UDP sent {sent} bytes")
                except Exception as e:
                    print(f"[ERROR] UDP sendto failed: {e}")
            elif self.outport and hasattr(self.outport, 'send'):
                print(f"[DEBUG] outport.send: {msg}")
                self.outport.send(msg)
        except Exception as e:
            print(f"[FATAL ERROR] send_mido_message exception: {e}")

    def send_midi_file(self, midi_file, on_finished=None, on_log=None):
        self.log_message.emit(f"[MIDI LOG] send_midi_file called: {midi_file}")
        print("[MIDI LOG] send_midi_file called")
        from workers import MidiSendWorker
        if not self.outport:
            raise RuntimeError("No MIDI Out port selected.")
        # Stop any existing worker
        if hasattr(self, '_midi_file_worker') and self._midi_file_worker and self._midi_file_worker.isRunning():
            self._midi_file_worker.stop()
            self._midi_file_worker.wait()
        # Send "All Notes Off" to all channels
        for ch in range(16):
            self.send_cc(ch, 123, 0)
        filename = getattr(midi_file, 'filename', None)
        if filename:
            desc = filename
        else:
            desc = 'in-memory MIDI file' if hasattr(midi_file, 'tracks') else str(midi_file)
        print(f"[MIDI LOG] Starting MIDI file send: {desc}")
        self._midi_file_worker = MidiSendWorker(self.outport, midi_file)
        if on_log:
            self._midi_file_worker.log.connect(on_log)
        if on_finished:
            self._midi_file_worker.finished.connect(on_finished)
        self._midi_file_worker.start()

    def stop_midi_file(self):
        self.log_message.emit("[MIDI LOG] stop_midi_file called")
        print("[MIDI LOG] stop_midi_file called")
        if hasattr(self, '_midi_file_worker') and self._midi_file_worker and self._midi_file_worker.isRunning():
            self._midi_file_worker.stop()
            self._midi_file_worker.wait()

    @property
    def current_input_port_name(self):
        return self._current_input_port_name

    @property
    def current_output_port_name(self):
        return self._current_output_port_name