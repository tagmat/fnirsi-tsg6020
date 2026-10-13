"""
FNIRSI TSG6020 / TSG3020 - SCPI probe (read-only)

Sends only the identification query *IDN? and prints any reply.
It does NOT change any setting on the instrument.

Setup (normal power-on, NOT firmware-update mode):
    pip install pyserial pyvisa pyvisa-py pyusb libusb-package
    python tsg_scpi_probe.py                          # probe all serial ports
    python tsg_scpi_probe.py /dev/cu.usbserial-XXXX   # macOS: one port only
    python tsg_scpi_probe.py COM5                     # Windows: one port only
"""
import os
import sys
import time

QUERY = "*IDN?"
PORT = sys.argv[1] if len(sys.argv) > 1 else None  # e.g. /dev/cu.usbserial-1410 or COM5
BAUDS = [115200, 9600, 57600, 38400, 19200]
TERMS = ["\n", "\r\n", "\r"]


def probe_serial():
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        print("[serial] pyserial not installed, skipping")
        return False

    ports = list(list_ports.comports())
    if PORT:
        ports = [p for p in ports if p.device == PORT] or [type("P", (), {"device": PORT, "description": "given", "vid": None, "pid": None})()]
    else:  # skip macOS built-ins that are never the generator
        ports = [p for p in ports if not any(s in p.device for s in ("Bluetooth", "debug-console", "wlan"))]
    if not ports:
        print("[serial] no COM ports found")
        return False

    found = False
    for p in ports:
        print(f"[serial] {p.device}: {p.description}  VID:PID={p.vid}:{p.pid}")
        for baud in BAUDS:
            for term in TERMS:
                try:
                    with serial.Serial(p.device, baud, timeout=0.6) as s:
                        s.reset_input_buffer()
                        s.write((QUERY + term).encode())
                        time.sleep(0.3)
                        reply = s.read(256)
                except Exception as e:
                    print(f"    open failed at {baud}: {e}")
                    break
                if reply:
                    print(f"    REPLY @ {baud} baud, term={term!r}: {reply!r}")
                    found = True
                    break
            if found:
                break
        if not found:
            print("    no reply on this port")
    return found


def probe_visa():
    # Make the libusb DLL from the libusb-package wheel visible to pyusb/pyvisa-py.
    try:
        import libusb_package
        libdir = os.path.dirname(str(libusb_package.get_library_path()))
        os.environ["PATH"] = libdir + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(libdir)
    except Exception:
        pass

    try:
        import pyvisa
    except ImportError:
        print("[visa] pyvisa not installed, skipping")
        return False

    try:
        rm = pyvisa.ResourceManager("@py")
    except Exception as e:
        print(f"[visa] could not start pyvisa-py backend: {e}")
        return False

    resources = rm.list_resources()
    usb = [r for r in resources if r.startswith("USB")]
    print(f"[visa] resources: {resources or 'none'}")
    if not usb:
        print("[visa] no USBTMC instrument found")
        return False

    found = False
    for r in usb:
        try:
            inst = rm.open_resource(r, timeout=2000)
            reply = inst.query(QUERY).strip()
            print(f"    {r} -> {reply}")
            found = True
        except Exception as e:
            print(f"    {r} -> no reply ({e})")
    return found


if __name__ == "__main__":
    print(f"Python {sys.version.split()[0]}  - probing with {QUERY}\n")
    ok_serial = probe_serial()
    print()
    ok_visa = probe_visa()
    print()
    if ok_serial or ok_visa:
        print("RESULT: the instrument answered. SCPI (or a text protocol) is likely supported.")
    else:
        print("RESULT: no reply. Check Device Manager for how the TSG enumerates "
              "(COM port, 'USB Test and Measurement Device', or 'Unknown device').")
