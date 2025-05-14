import mido
from mido import MidiFile, Message
from workers import MidiMessageSendWorker

class MIDIHandler:
    def __init__(self):
        self.inport = None
        self.outport = None
        self.midi_send_worker = None

    def list_input_ports(self):
        return mido.get_input_names()

    def list_output_ports(self):
        return mido.get_output_names()

    def open_input(self, port_name):
        if self.inport:
            self.inport.close()
        self.inport = mido.open_input(port_name)

    def open_output(self, port_name):
        if self.outport:
            self.close_output_worker()
            self.outport.close()
        self.outport = mido.open_output(port_name)
        self.midi_send_worker = MidiMessageSendWorker(self.outport)
        self.midi_send_worker.start()

    def close_output_worker(self):
        if self.midi_send_worker:
            self.midi_send_worker.stop()
            self.midi_send_worker = None

    def close(self):
        if self.inport:
            self.inport.close()
        if self.outport:
            self.close_output_worker()
            self.outport.close()

    def send_sysex(self, data):
        if self.outport and self.midi_send_worker:
            print(f"[MIDI LOG] Sending SysEx: {' '.join(f'{b:02X}' for b in data)}")
            # Remove 0xF0 and 0xF7 if present
            if data and data[0] == 0xF0:
                data = data[1:]
            if data and data[-1] == 0xF7:
                data = data[:-1]
            msg = Message('sysex', data=data)
            self.midi_send_worker.send(msg)

    def receive_sysex(self, callback):
        if self.inport:
            for msg in self.inport.iter_pending():
                if msg.type == 'sysex':
                    # Ensure F0/F7 are present for incoming SysEx
                    data = list(msg.data)
                    if not (data and data[0] == 0xF0):
                        data = [0xF0] + data
                    if not (data and data[-1] == 0xF7):
                        data = data + [0xF7]
                    callback(data)

    def send_custom_midi_command(self, cmd, values):
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
            msg = Message('sysex', data=sysex_bytes[1:-1])
            self.midi_send_worker.send(msg)
            return
        elif status == 0xF0:
            data = [status] + params
            if data[0] == 0xF0:
                data = data[1:]
            if data and data[-1] == 0xF7:
                data = data[:-1]
            sysex_bytes = [0xF0] + data + [0xF7]
            msg = Message('sysex', data=sysex_bytes[1:-1])
            self.midi_send_worker.send(msg)
            return
        else:
            if cmd["parameters"] and cmd["parameters"][0]["name"].lower() == "channel":
                channel = params.pop(0)
                status = (status & 0xF0) | ((channel - 1) & 0x0F)
            data = [status] + params
            msg = Message.from_bytes(data)
            self.midi_send_worker.send(msg)
            return

    def get_command_hex(self, cmd, values):
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
        # ...existing code for non-template commands...
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
        if self.outport and self.midi_send_worker:
            print(f"[MIDI LOG] Sending CC: channel={channel+1} control={control} value={value}")
            import mido
            msg = mido.Message('control_change', channel=channel, control=control, value=value)
            self.midi_send_worker.send(msg)
