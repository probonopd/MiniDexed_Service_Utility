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
    import os

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Load bundled fonts for Alpine musl builds
    if hasattr(sys, '_MEIPASS') or os.path.exists('./fonts'):
        # We're running from a bundled executable, load fonts
        from PySide6.QtGui import QFontDatabase
        font_db = QFontDatabase()
        
        # Check for bundled fonts directory
        fonts_dir = './fonts'
        if os.path.exists(fonts_dir):
            print(f"Loading bundled fonts from {fonts_dir}")
            for root, dirs, files in os.walk(fonts_dir):
                for file in files:
                    if file.endswith(('.ttf', '.otf')):
                        font_path = os.path.join(root, file)
                        font_id = font_db.addApplicationFont(font_path)
                        if font_id != -1:
                            families = font_db.applicationFontFamilies(font_id)
                            print(f"Loaded font: {families}")
        
        # Set FONTCONFIG environment variables to use bundled fonts
        if os.path.exists('./etc/fonts'):
            os.environ['FONTCONFIG_PATH'] = './etc/fonts'
        if os.path.exists('./share/fontconfig'):
            os.environ['FONTCONFIG_FILE'] = './etc/fonts/fonts.conf'

    from midi_handler import MIDIHandler
    midi_handler = MIDIHandler()  # or your actual initialization
    app.midi_handler = midi_handler  # Set as global

    # Check if UDP port 50007 is open
    udp_port = 50007
    udp_host = '127.0.0.1'
    udp_available = is_udp_port_open(udp_port, udp_host)

    from main_window import MainWindow
    window = MainWindow(midi_handler=midi_handler)
    if udp_available:
        # Offer UDP Socket as an option in your MIDI input/output selection UI
        # This is a placeholder: you must implement the UI logic in main_window.py or midi_handler.py
        print(f"UDP Socket available on {udp_host}:{udp_port}. Offer as MIDI In/Out option.")
        # Example: midi_handler.add_udp_port(udp_host, udp_port)
        # You must implement add_udp_port in MIDIHandler to handle sending/receiving MIDI via UDP
    window.show()
    sys.exit(app.exec())
