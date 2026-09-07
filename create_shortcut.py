import os
import sys
import ctypes
import subprocess

AUMID = "JinsakaiCorp.ImgLab.1"
APP_NAME = "ImgLab"
SCRIPT = "ImgLab.py"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(BASE_DIR, "assets", "imglab_icon.ico")
HOME = os.path.expanduser("~")

DESKTOPS = []
od = os.path.join(HOME, "OneDrive", "Desktop")
if os.path.isdir(od):
    DESKTOPS.append(od)
DESKTOPS.append(os.path.join(HOME, "Desktop"))


def find_pythonw():
    exe = os.path.join(sys.executable, "..", "pythonw.exe")
    exe = os.path.abspath(exe)
    if os.path.exists(exe):
        return exe
    alt = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if os.path.exists(alt):
        return alt
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Python"),
    ]
    for base in candidates:
        if not os.path.isdir(base):
            continue
        for p in sorted(os.listdir(base), reverse=True):
            cand = os.path.join(base, p, "pythonw.exe")
            if os.path.exists(cand):
                return cand
    return None


def main():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(AUMID)
    except Exception:
        pass

    pythonw = find_pythonw()
    if not pythonw:
        print("[ERROR] pythonw.exe tidak ditemukan.")
        sys.exit(1)

    target = pythonw
    args = '"%s"' % os.path.join(BASE_DIR, SCRIPT)
    icon = ICON if os.path.exists(ICON) else pythonw

    import win32com.client
    shell = win32com.client.Dispatch("WScript.Shell")
    ok = 0
    for desk in DESKTOPS:
        lnk = os.path.join(desk, APP_NAME + ".lnk")
        s = shell.CreateShortcut(lnk)
        s.TargetPath = target
        s.Arguments = args
        s.IconLocation = icon
        s.WorkingDirectory = BASE_DIR
        s.Description = "ImgLab - Image Toolkit"
        s.Save()
        ok += 1
        print("[%s] Shortcut dibuat di %s" % ("SUCCESS" if os.path.exists(lnk) else "FAIL", lnk))
    print("Shortcut %s berhasil dibuat di Desktop!" % APP_NAME)
    if ok:
        subprocess.Popen("explorer.exe /select,\"%s\"" % os.path.join(DESKTOPS[0], APP_NAME + ".lnk"))


if __name__ == "__main__":
    main()