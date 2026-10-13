"""
FNIRSI TSG6020 / TSG3020 - SCPI write test (UNI-T UTG900-style commands)

Safe by design:
  * reads and saves the current CH1 settings first
  * keeps CH1 output OFF while writing and reading back test values
  * restores the saved settings at the end (also on Ctrl+C / errors)
  * only touches CH1, never MODe, LOAD, ARB or CH2

Optional: --output enables CH1 for a few seconds at 1 Vpp / 1 kHz sine so
you can watch it on a scope, then switches it off again. Disconnect any
sensitive load from CH1 before using it.

    pip install pyserial
    python3 tsg_scpi_write_test.py /dev/cu.usbmodemXXXX
    python3 tsg_scpi_write_test.py /dev/cu.usbmodemXXXX --output
"""
import sys
import time

import serial

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args:
    sys.exit(__doc__)
PORT = args[0]
DO_OUTPUT = "--output" in sys.argv
BAUD = 115200
CH = ":CHANnel1"

# (setting, command suffix, test value, numeric?)
FIELDS = [
    ("waveform",  ":BASE:WAVe",      "SQUare", False),
    ("frequency", ":BASE:FREQuency", "12345.6", True),
    ("amplitude", ":BASE:AMPLitude", "1.234",   True),
    ("offset",    ":BASE:OFFSet",    "0.1",     True),
    ("phase",     ":BASE:PHAse",     "45",      True),
    ("duty",      ":BASE:DUTY",      "25",      True),
]


def query(s, cmd):
    s.reset_input_buffer()
    s.write((cmd + "\n").encode())
    time.sleep(0.15)
    out = b""
    end = time.time() + 1.0
    while time.time() < end:
        c = s.read(256)
        if c:
            out += c
            end = time.time() + 0.1
        elif out:
            break
    return out.decode(errors="replace").strip()


def write(s, cmd):
    s.write((cmd + "\n").encode())
    time.sleep(0.15)


def same(a, b, numeric):
    if not numeric:
        return a.strip().upper().startswith(b.strip().upper()[:3])
    try:
        return abs(float(a) - float(b)) <= max(1e-6, abs(float(b)) * 1e-4)
    except ValueError:
        return False


with serial.Serial(PORT, BAUD, timeout=0.2) as s:
    idn = query(s, "*IDN?")
    if not idn:
        sys.exit("No reply to *IDN? - check the port and that the TSG is in normal mode.")
    print("Connected:", idn.split(",")[0], idn.split(",")[1] if "," in idn else "")

    saved = {name: query(s, CH + suf + "?") for name, suf, _, _ in FIELDS}
    saved_out = query(s, CH + ":OUTPut?")
    print("\nSaved CH1 settings:")
    for k, v in saved.items():
        print(f"  {k:10s} {v}")
    print(f"  {'output':10s} {saved_out}")

    results = []
    try:
        write(s, CH + ":OUTPut OFF")
        print("\nWrite / read-back test (output OFF):")
        for name, suf, val, num in FIELDS:
            write(s, f"{CH}{suf} {val}")
            back = query(s, CH + suf + "?")
            ok = same(back, val, num)
            results.append((name, ok))
            print(f"  {'OK ' if ok else 'XX '}{name:10s} sent {val:10s} read {back}")

        if DO_OUTPUT:
            print("\nOutput test: CH1 sine 1 kHz 1 Vpp, ON for 5 s ...")
            for suf, val in [(":BASE:WAVe", "SINe"), (":BASE:FREQuency", "1000"),
                             (":BASE:AMPLitude", "1"), (":BASE:OFFSet", "0")]:
                write(s, f"{CH}{suf} {val}")
            write(s, CH + ":OUTPut ON")
            print("  output now:", query(s, CH + ":OUTPut?"))
            time.sleep(5)
            write(s, CH + ":OUTPut OFF")
            print("  output now:", query(s, CH + ":OUTPut?"))
    finally:
        print("\nRestoring saved settings ...")
        write(s, CH + ":OUTPut OFF")
        for name, suf, _, _ in FIELDS:
            if saved[name]:
                write(s, f"{CH}{suf} {saved[name]}")
        if saved_out.upper().startswith("ON"):
            write(s, CH + ":OUTPut ON")
        restored = all(same(query(s, CH + suf + "?"), saved[n], num)
                       for n, suf, _, num in FIELDS if saved[n])
        print("  restored:", "yes" if restored else "CHECK MANUALLY")

    passed = sum(ok for _, ok in results)
    print(f"\nResult: {passed}/{len(results)} settings written and read back correctly.")
