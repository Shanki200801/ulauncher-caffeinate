#!/usr/bin/env python3
"""caffeinate — keep the screen on and the laptop awake (Cinnamon/GNOME session).

  caffeinate            stay awake until turned off
  caffeinate 90         stay awake for 90 minutes   (also: 30m, 2h, 1h30m)
  caffeinate off        turn it off
  caffeinate status     print current state

Works by holding an org.gnome.SessionManager inhibit (idle + suspend) in a small
background process (GNOME, Cinnamon, MATE, Budgie…). If that service isn't
available it falls back to `systemd-inhibit`. The inhibit ends when the process exits.
"""
import os
import re
import signal
import sys
import time

STATE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "ulauncher-caffeinate.state")


def read_state():
    try:
        pid, until = open(STATE).read().split()
        pid, until = int(pid), float(until)
        os.kill(pid, 0)
        return pid, until
    except Exception:
        return None


def status_text():
    st = read_state()
    if not st:
        return "off"
    _, until = st
    if until == 0:
        return "on (until turned off)"
    left = max(0, -(-int(until - time.time()) // 60))
    h, m = divmod(left, 60)
    return f"on ({h}h {m}m left)" if h else f"on ({m}m left)"


def stop():
    st = read_state()
    if st:
        try:
            os.kill(st[0], signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        os.remove(STATE)
    except FileNotFoundError:
        pass


def parse_minutes(arg):
    if arg.isdigit():
        return int(arg)
    m = re.fullmatch(r"(?:(\d+)h)?\s*(?:(\d+)m)?", arg.strip().lower())
    if not m or not any(m.groups()):
        sys.exit(f"caffeinate: can't understand duration {arg!r} (try 30, 45m, 2h, 1h30m)")
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def hold(minutes):
    """Runs in the detached child: inhibit, then wait."""
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        # flags: 4 = suspend, 8 = idle (screen blank / screensaver)
        bus.call_sync(
            "org.gnome.SessionManager", "/org/gnome/SessionManager", "org.gnome.SessionManager",
            "Inhibit", GLib.Variant("(susu)", ("caffeinate", 0, "Caffeinate is on", 4 | 8)),
            GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, -1, None,
        )
    except GLib.Error:
        # No session manager: let systemd-inhibit hold the lock while we live.
        import subprocess
        subprocess.Popen(["systemd-inhibit", "--what=idle:sleep", "--who=caffeinate",
                          "--why=Caffeinate is on", "--mode=block",
                          "sh", "-c", f"while kill -0 {os.getpid()} 2>/dev/null; do sleep 5; done"])
    loop = GLib.MainLoop()
    signal.signal(signal.SIGTERM, lambda *_: loop.quit())
    if minutes:
        GLib.timeout_add_seconds(minutes * 60, loop.quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, loop.quit)
    loop.run()
    try:
        if read_state() and read_state()[0] == os.getpid():
            os.remove(STATE)
    except Exception:
        pass


def start(minutes):
    stop()
    until = time.time() + minutes * 60 if minutes else 0
    pid = os.fork()
    if pid:
        open(STATE, "w").write(f"{pid} {until}")
        return
    os.setsid()
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    hold(minutes)
    os._exit(0)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg in ("-h", "--help"):
        print(__doc__.strip())
    elif arg == "off":
        stop()
        print("caffeinate: off")
    elif arg == "status":
        print(status_text())
    elif arg == "toggle":
        if read_state():
            stop()
            print("caffeinate: off")
        else:
            start(0)
            time.sleep(0.3)
            print("caffeinate: on")
    else:
        minutes = parse_minutes(arg) if arg else 0
        start(minutes)
        time.sleep(0.3)
        print("caffeinate:", status_text())


if __name__ == "__main__":
    main()
