#!/bin/env python3
# -*- coding: utf-8 -*-
# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --include-package=zeroconf
# nuitka-project: --include-package=rtmidi
# nuitka-project: --include-package=mido.backends.rtmidi
# nuitka-project: --include-data-dir=src/midi_commands=midi_commands
# nuitka-project: --include-data-dir=src/data=data
# nuitka-project: --include-data-dir=src/images=images
# nuitka-project: --prefer-source-code

from PySide6.QtWidgets import QApplication
import socket
import logging # Add this line

logging.getLogger('comtypes').setLevel(logging.WARNING) # Add this line

def is_udp_port_open(port, host='127.0.0.1'):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.2)
        sock.sendto(b'ping', (host, port))
        # Try to receive a response (non-blocking)
        try:
            sock.recvfrom(1024)
        except Exception:
            pass
        sock.close()
        return True  # If no exception, port is open (or at least not blocked)
    except Exception:
        return False

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    from midi_handler import MIDIHandler
    midi_handler = MIDIHandler()  # or your actual initialization
    app.midi_handler = midi_handler  # Set as global

    # Check if UDP port 50007 is open
    udp_port = 50007
    udp_host = '127.0.0.1'
    udp_available = is_udp_port_open(udp_port, udp_host)

    from main_window import MainWindow
    window = MainWindow()
    if udp_available:
        # Offer UDP MIDI as an option in your MIDI input/output selection UI
        # This is a placeholder: you must implement the UI logic in main_window.py or midi_handler.py
        print(f"UDP MIDI available on {udp_host}:{udp_port}. Offer as MIDI In/Out option.")
        # Example: midi_handler.add_udp_port(udp_host, udp_port)
        # You must implement add_udp_port in MIDIHandler to handle sending/receiving MIDI via UDP
    window.show()
    sys.exit(app.exec())
