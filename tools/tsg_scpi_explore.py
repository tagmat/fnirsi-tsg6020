"""
FNIRSI TSG6020 / TSG3020 - SCPI dialect explorer (QUERIES ONLY)

Sends only query commands (ending in '?') from several known SCPI dialects
and prints which ones the generator answers. Nothing is set or changed.

    pip install pyserial
    python3 tsg_scpi_explore.py /dev/cu.usbserial-XXXX        # macOS
    python3 tsg_scpi_explore.py COM5                          # Windows
    python3 tsg_scpi_explore.py /dev/cu.usbserial-XXXX 9600   # force baud
"""
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__)
BAUDS = [int(sys.argv[2])] if len(sys.argv) > 2 else [115200, 9600, 57600, 38400, 19200]

CANDIDATES = {
    "IEEE 488.2 common": [
        "*IDN?", "*OPT?", "*ESR?", "*STB?",
    ],
    "SCPI system": [
        "SYSTem:ERRor?", "SYSTem:VERSion?",
    ],
    # UNI-T UTG900/UTG900E (the TSG manual references UTG932/UTG962)
    "UNI-T UTG900 style": [
        ":CHANnel1:BASE:WAVe?", ":CHANnel1:BASE:FREQuency?", ":CHANnel1:BASE:AMPLitude?",
        ":CHANnel1:BASE:OFFSet?", ":CHANnel1:BASE:PHAse?", ":CHANnel1:BASE:DUTY?",
        ":CHANnel1:OUTPut?", ":CHANnel1:LOAD?", ":CHANnel1:MODe?", ":CHANnel1:ARB:INDex?",
        ":CHANnel2:BASE:FREQuency?", ":CHANnel2:OUTPut?",
    ],
    # Generic SCPI (Keysight / Rigol style)
    "Generic SCPI SOURce": [
        ":SOURce1:FUNCtion?", ":SOURce1:FREQuency?", ":SOURce1:VOLTage?",
        ":SOURce1:VOLTage:OFFSet?", ":OUTPut1?", "FREQ?", "FUNC?", "VOLT?", "OUTP?",
    ],
    # Siglent SDG style
    "Siglent style": [
        "C1:BSWV?", "C1:OUTP?",
    ],
    # Frequency counter (TSG has a built-in counter)
    "Counter": [
        ":COUNter:FREQuency?", ":COUNter:STATe?", "MEASure:FREQuency?",
    ],
}


def ask(s, cmd, term):
    s.reset_input_buffer()
    s.write((cmd + term).encode())
    time.sleep(0.25)
    out = b""
    deadline = time.time() + 0.8
    while time.time() < deadline:
        chunk = s.read(256)
        if chunk:
            out += chunk
            deadline = time.time() + 0.15
        elif out:
            break
    return out.decode(errors="replace").strip()


def find_link():
    for baud in BAUDS:
        for term in ("\n", "\r\n", "\r"):
            with serial.Serial(PORT, baud, timeout=0.2) as s:
                r = ask(s, "*IDN?", term)
            if r:
                return baud, term, r
    sys.exit("No reply to *IDN? on any baud/terminator. Check the port name.")


baud, term, idn = find_link()
print(f"Link: {PORT} @ {baud} baud, terminator {term!r}")
print(f"*IDN? -> {idn}\n")

answered = {}
with serial.Serial(PORT, baud, timeout=0.2) as s:
    for group, cmds in CANDIDATES.items():
        print(f"== {group}")
        for c in cmds:
            r = ask(s, c, term)
            mark = "OK " if r else "-- "
            print(f"  {mark}{c:32s} {r}")
            if r:
                answered.setdefault(group, []).append(c)
        print()

print("Summary (groups with answers):")
for g, cmds in answered.items():
    print(f"  {g}: {len(cmds)} answered")
if not answered:
    print("  only *IDN? answered - the command set is probably proprietary.")
