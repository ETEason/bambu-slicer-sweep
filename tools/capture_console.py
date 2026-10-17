"""Run a command in a hidden new console and dump that console's screen buffer.

Bambu Studio's Windows executable writes CLI text (e.g. --help) straight to the
console, so stdout/stderr redirection captures nothing. This helper reads the
console buffer instead.

Usage: python tools/capture_console.py OUTFILE -- EXE [ARGS...]
"""
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class COORD(ctypes.Structure):
    _fields_ = [("X", wt.SHORT), ("Y", wt.SHORT)]


class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", wt.SHORT), ("Top", wt.SHORT), ("Right", wt.SHORT), ("Bottom", wt.SHORT)]


class CSBI(ctypes.Structure):
    _fields_ = [("dwSize", COORD), ("dwCursorPosition", COORD), ("wAttributes", wt.WORD),
                ("srWindow", SMALL_RECT), ("dwMaximumWindowSize", COORD)]


def read_console(pid: int) -> str:
    k32.FreeConsole()
    if not k32.AttachConsole(pid):
        raise OSError(ctypes.get_last_error(), "AttachConsole failed")
    try:
        h = k32.CreateFileW("CONOUT$", 0xC0000000, 3, None, 3, 0, None)
        info = CSBI()
        k32.GetConsoleScreenBufferInfo(h, ctypes.byref(info))
        width, lines = info.dwSize.X, info.dwCursorPosition.Y + 1
        out = []
        buf = ctypes.create_unicode_buffer(width)
        n = wt.DWORD()
        for y in range(lines):
            k32.ReadConsoleOutputCharacterW(h, buf, width, COORD(0, y), ctypes.byref(n))
            out.append(buf.value[: n.value].rstrip())
        k32.CloseHandle(h)
        return "\n".join(out).rstrip() + "\n"
    finally:
        k32.FreeConsole()


def main() -> None:
    outfile = sys.argv[1]
    cmd = sys.argv[sys.argv.index("--") + 1:]
    # A cmd.exe host keeps the console alive after the target exits, so the buffer can be read.
    # A large buffer height keeps long help text from scrolling away.
    script = subprocess.list2cmdline(cmd) + " & echo __DONE__ & ping -n 30 127.0.0.1 >nul"
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    # Pass a raw command line: cmd.exe /s /c strips only the outer quotes.
    host = subprocess.Popen('cmd.exe /s /c "mode con: cols=200 lines=9999 >nul & ' + script + '"',
                            creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=si)
    try:
        deadline = time.time() + 120
        text = ""
        while time.time() < deadline:
            time.sleep(1)
            text = read_console(host.pid)
            if "__DONE__" in text:
                break
        text = text.replace("__DONE__", "").rstrip() + "\n"
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {outfile}: {len(text.splitlines())} lines")
    finally:
        # Kill the whole tree we started (cmd.exe and its ping child).
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(host.pid)], capture_output=True)
        host.wait()


if __name__ == "__main__":
    main()
