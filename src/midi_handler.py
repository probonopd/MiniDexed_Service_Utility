import mido
from mido import MidiFile, Message
from workers import MidiMessageSendWorker

class MIDIHandler:
    def __init__(self):
        self.inport = None
        self.outport = None
        self._midi_send_worker = None
        self._midi_file_worker = None
        self._input_callbacks = {}

    def list_input_ports(self):
        print("[MIDI LOG] list_input_ports called")
        return mido.get_input_names()

    def list_output_ports(self):
        print("[MIDI LOG] list_output_ports called")
        return mido.get_output_names()

    def open_input(self, port_name):
        print("[MIDI LOG] open_input called")
        if self.inport:
            self.inport.close()
        self.inport = mido.open_input(port_name)

    def open_output(self, port_name):
        print("[MIDI LOG] open_output called")
        if self.outport:
            self.close_output_worker()
            self.outport.close()
        self.outport = mido.open_output(port_name)
        self._midi_send_worker = MidiMessageSendWorker(self.outport)
        self._midi_send_worker.start()

    def close_output_worker(self):
        print("[MIDI LOG] close_output_worker called")
        if self._midi_send_worker:
            self._midi_send_worker.stop()
            self._midi_send_worker = None

    def close(self):
        print("[MIDI LOG] close called")
        if self.inport:
            self.inport.close()
        if self.outport:
            self.close_output_worker()
            self.outport.close()

    def send_sysex(self, data):
        print("[MIDI LOG] send_sysex called")
        if self.outport and self._midi_send_worker:
            print(f"[MIDI LOG] Sending SysEx: {' '.join(f'{b:02X}' for b in data)}")
            # Remove 0xF0 and 0xF7 if present
            if data and data[0] == 0xF0:
                data = data[1:]
            if data and data[-1] == 0xF7:
                data = data[:-1]
            msg = Message('sysex', data=data)
            self._midi_send_worker.send(msg)

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
        print("[MIDI LOG] send_cc called")
        if self.outport:
            print(f"[MIDI LOG] Sending CC: channel={channel+1} control={control} value={value}")
            import mido
            msg = mido.Message('control_change', channel=channel, control=control, value=value)
            if hasattr(self.outport, 'send'):
                self.outport.send(msg)

    def send_midi_file(self, midi_file, on_finished=None, on_log=None):
        print("[MIDI LOG] send_midi_file called")
        from workers import MidiSendWorker
        if not self.outport:
            raise RuntimeError("No MIDI Out port selected.")
        # Stop any existing worker
        if hasattr(self, '_midi_file_worker') and self._midi_file_worker and self._midi_file_worker.isRunning():
            self._midi_file_worker.stop()
            self._midi_file_worker.wait()
        # Improved logging: show filename if available, else a description
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
        print("[MIDI LOG] stop_midi_file called")
        if hasattr(self, '_midi_file_worker') and self._midi_file_worker and self._midi_file_worker.isRunning():
            self._midi_file_worker.stop()
            self._midi_file_worker.wait()
