"""Render raws in Phocus without its GUI, through its hot folder.

Phocus exports every raw that appears in the folder its browser shows when AutoExport is on. On launch
it shows the last folder in its ThumbnailsRecent list (macOS bookmarks), so the helper appends a
bookmark for a private watch folder there. It exports using the settings in the raw's .phos sidecar if one is there first. This module
backs up Phocus's preferences, points it at a private watch folder, renders, and restores the
preferences afterwards (and relaunches Phocus if it was running). Raws are copied into the watch folder,
never moved; the originals are only read. Don't use Phocus while it runs.

    from phocus_hotfolder import HotFolder
    with HotFolder() as hf:
        tif = hf.render("some.3fr", LensCorrection=4)      # ImageCorrection keys to change

Exports are 16-bit ProPhoto TIFFs at 50% (the template's output preset), named by Phocus. Without a
root, the helper works in a temporary folder under ~/Pictures and deletes it on exit, so move exports
out first.
"""
import os
import plistlib
import shutil
import subprocess
import tempfile
import time
import base64
import uuid

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phocus_standard.phos")
DOMAIN = "dk.hasselblad.phocus"


def _running():
    return subprocess.run(["pgrep", "-x", "Phocus"], capture_output=True).returncode == 0


def set_landscape(path):
    """Orientation 1 in the flat copy, so Phocus exports it in sensor orientation like the raw data."""
    import struct
    import tifffile
    with tifffile.TiffFile(path) as t:
        tag = t.pages[0].tags.get("Orientation")
        if tag is None or tag.value == 1:
            return
        off = tag.valueoffset
    with open(path, "r+b") as f:
        f.seek(off)
        f.write(struct.pack("<H", 1))


def set_baseline_exposure(path, value=0.0):
    """Write BaselineExposure into a raw copy (IFD0 SRATIONAL)."""
    import struct
    import tifffile
    with tifffile.TiffFile(path) as t:
        tag = t.pages[0].tags.get("BaselineExposure")
        if tag is None:
            return
        off = tag.valueoffset
    with open(path, "r+b") as f:
        f.seek(off)
        f.write(struct.pack("<ii", int(round(value * 1_000_000)), 1_000_000))


def set_reference_body(path, g1=2.600, g2=2.260):
    """Write the reference body's two factory gains into a raw copy's GAIN record (maker note 0x0019, bytes
    84-87), so Phocus renders it as the body the profiles were fitted on (Findings 13, 16, 35). Phocus doesn't
    check the record's checksum. Other bodies are then corrected in the Capture One settings file."""
    import numpy as np
    from makernote_transplant import entries
    e = entries(path).get(0x0019)
    if e is None or e["raw"][:4] != b"GAIN":
        return
    with open(path, "r+b") as f:
        f.seek(e["loc"] + 84)
        f.write(np.array([g1, g2], "<f2").tobytes())


def _bookmark(path):
    js = ('ObjC.import("Foundation"); var u = $.NSURL.fileURLWithPath("%s"); '
          'u.bookmarkDataWithOptionsIncludingResourceValuesForKeysRelativeToURLError(0, $(), $(), null)'
          '.base64EncodedStringWithOptions(0).js' % path.replace('"', '\\"'))
    out = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True, check=True).stdout.strip()
    return base64.b64decode(out)


def _quit():
    subprocess.run(["pkill", "-TERM", "-x", "Phocus"], capture_output=True)
    for _ in range(40):
        if not _running():
            return
        time.sleep(0.5)
    raise RuntimeError("Phocus didn't quit")


class HotFolder:
    def __init__(self, root=None, wait=12):
        # under ~/Pictures: macOS may not let Phocus read ~/Documents or other protected folders
        self.owns_root = root is None
        self.root = root or tempfile.mkdtemp(prefix="HNCS hot folder ", dir=os.path.expanduser("~/Pictures"))
        self.watch = os.path.join(self.root, "watch")
        self.out = os.path.join(self.root, "export")
        self.wait = wait

    def __enter__(self):
        os.makedirs(self.watch, exist_ok=True)
        os.makedirs(self.out, exist_ok=True)
        self.backup = os.path.join(self.root, "phocus-prefs-backup.plist")
        subprocess.run(["defaults", "export", DOMAIN, self.backup], check=True)
        self.was_running = _running()
        if self.was_running:
            _quit()
        prefs = plistlib.load(open(self.backup, "rb"))
        prefs["AutoExport"] = 1
        prefs["exportDirectory"] = self.out
        prefs["ActiveTabs"] = [self.watch]
        prefs["ThumbnailsRecent"] = list(prefs.get("ThumbnailsRecent", [])) + [{"Bookmark": _bookmark(self.watch)}]
        mod = os.path.join(self.root, "phocus-prefs-hotfolder.plist")
        plistlib.dump(prefs, open(mod, "wb"), fmt=plistlib.FMT_BINARY)
        subprocess.run(["defaults", "import", DOMAIN, mod], check=True)
        subprocess.run(["open", "-a", "Phocus"], check=True)
        time.sleep(self.wait)
        return self

    def __exit__(self, *exc):
        if _running():
            _quit()
        subprocess.run(["defaults", "import", DOMAIN, self.backup], check=True)
        if self.owns_root:  # move exports out before leaving the with block
            shutil.rmtree(self.root, ignore_errors=True)
        if self.was_running:
            for _ in range(5):  # right after quitting, Launch Services can refuse (-600); retry
                if subprocess.run(["open", "-a", "Phocus"], capture_output=True).returncode == 0:
                    break
                time.sleep(3)
        return False

    def _exports(self):
        d = os.path.join(self.out, "Previews")
        return set(os.listdir(d)) if os.path.isdir(d) else set()

    def render(self, raw, name=None, timeout=120, **settings):
        """Copy RAW (with a sidecar carrying SETTINGS) into the watch folder; return the export's path."""
        name = name or os.path.basename(raw)
        p = plistlib.load(open(TEMPLATE, "rb"))
        p["GUID"] = str(uuid.uuid4()).upper()
        for k, v in settings.items():
            p["ImageSettings"][0]["ImageCorrection"][k] = v
        before = self._exports()
        plistlib.dump(p, open(os.path.join(self.watch, name + ".phos"), "wb"), fmt=plistlib.FMT_XML)
        time.sleep(1)
        tmp = os.path.join(self.root, "." + name)
        shutil.copyfile(raw, tmp)
        os.replace(tmp, os.path.join(self.watch, name))
        t0 = time.time()
        while time.time() - t0 < timeout:
            new = sorted(self._exports() - before)
            new = [n for n in new if n.endswith(".tif")]
            if new:
                path = os.path.join(self.out, "Previews", new[0])
                size, stable = -1, 0
                while stable < 2:  # Phocus creates the file empty and writes it a moment later
                    time.sleep(1.5)
                    cur = os.path.getsize(path)
                    stable = stable + 1 if (cur == size and cur > 1_000_000) else 0
                    size = cur
                    if time.time() - t0 > timeout:
                        raise TimeoutError(f"export for {name} never finished writing")
                for leftover in (os.path.join(self.watch, name), os.path.join(self.watch, name + ".phos")):
                    if os.path.exists(leftover):
                        os.remove(leftover)
                return path
            time.sleep(1)
        raise TimeoutError(f"no export for {name} within {timeout} s")

    def remove(self, *paths):
        for pth in paths:
            if pth and os.path.exists(pth) and os.path.realpath(pth).startswith(os.path.realpath(self.root)):
                os.remove(pth)
