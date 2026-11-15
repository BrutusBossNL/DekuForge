"""Shared leaf-green and forged-gold desktop styling."""

import math
import os
import struct
import tkinter as tk

from .core import ROOT

BG = "#08110b"
PANEL = "#13251a"
LEAF = "#9bbb49"
GOLD = "#e8b94f"
TEXT = "#f4e8c5"
MUTED = "#a5b292"
BORDER = "#344a28"
LOGO = ROOT / "assets" / "branding" / "logo.png"
ICON_PNG = ROOT / "assets" / "branding" / "icon.png"
ICON = ROOT / "assets" / "branding" / "launcher.ico"
BACKGROUND = ROOT / "assets" / "branding" / "background.png"


class BackgroundCanvas(tk.Canvas):
    """Static, darkened artwork behind normal, opaque interface controls."""

    def __init__(self, parent, *, surface=None, opacity=0.46, **options):
        super().__init__(parent, bg=BG, highlightthickness=0, borderwidth=0, **options)
        self._surface = surface
        self._opacity = opacity
        self._art = None
        self._fitted = None
        self._image = None
        self._resize_job = None
        self._item = self.create_image(0, 0, anchor="nw")
        if surface is None and BACKGROUND.is_file():
            try:
                from PIL import Image
                with Image.open(BACKGROUND) as source:
                    self._art = source.convert("RGB")
            except (ImportError, OSError):
                pass  # Plain forest styling remains usable without optional artwork.
        self.bind("<Configure>", self._schedule_resize, add="+")

    def _region(self):
        from PIL import Image, ImageOps
        size = (max(1, self.winfo_width()), max(1, self.winfo_height()))
        owner = self._surface or self
        if owner._art is None:
            return None
        owner_size = (max(1, owner.winfo_width()), max(1, owner.winfo_height()))
        if owner._fitted is None or owner._fitted.size != owner_size:
            owner._fitted = ImageOps.fit(owner._art, owner_size, method=Image.Resampling.LANCZOS)
        fitted = owner._fitted
        x = self.winfo_rootx() - owner.winfo_rootx()
        y = self.winfo_rooty() - owner.winfo_rooty()
        return Image.blend(Image.new("RGB", size, BG), fitted.crop((x, y, x + size[0], y + size[1])), self._opacity)

    def _schedule_resize(self, _event):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._redraw)

    def _redraw(self):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = None
        from io import BytesIO
        subdued = self._region()
        if subdued is None:
            return
        payload = BytesIO()
        subdued.save(payload, format="PNG")
        self._image = tk.PhotoImage(master=self, data=payload.getvalue(), format="png")
        self.itemconfigure(self._item, image=self._image)
        self.tag_lower(self._item)
        for child in self.winfo_children():
            if isinstance(child, BackgroundCanvas):
                if child._resize_job is not None:
                    child.after_cancel(child._resize_job)
                child._redraw()

    def destroy(self):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        super().destroy()


class ArtworkLabel(BackgroundCanvas):
    """Native Tk text over the matching backdrop crop, without opaque label boxes."""

    def __init__(self, parent, text, size, color, **options):
        owner = parent._surface or parent
        super().__init__(parent, surface=owner, opacity=parent._opacity)
        self._text_item = self.create_text(0, 0, text=text, fill=color, font=("Segoe UI", size),
                                           anchor="nw", justify="left", width=options.get("wraplength", 0))
        self._measure()

    def _measure(self):
        box = self.bbox(self._text_item)
        if box:
            super().configure(width=max(1, box[2] - box[0]) + 2, height=max(1, box[3] - box[1]) + 2)

    def configure(self, cnf=None, **options):
        if hasattr(self, "_text_item"):
            changes = {}
            if "text" in options:
                changes["text"] = options.pop("text")
            if "wraplength" in options:
                changes["width"] = options.pop("wraplength")
            if changes:
                self.itemconfigure(self._text_item, **changes)
                self._measure()
        return super().configure(cnf, **options)


def apply_identity():
    """Stop Windows grouping this window under the invoking terminal/editor."""
    if os.name == "nt":
        import ctypes
        call = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        call.argtypes = [ctypes.c_wchar_p]
        call.restype = ctypes.c_long
        result = call("DekuForge.Launcher")
        if result < 0:
            raise OSError(f"Could not set launcher identity: {result}")


def logo_image(master, width=650, height=310):
    return _png_image(master, LOGO, width, height)


def icon_image(master, width=64, height=64):
    return _png_image(master, ICON_PNG if ICON_PNG.is_file() else LOGO, width, height)


def _png_image(master, path, width, height):
    if not path.is_file():
        return None
    payload = path.read_bytes()
    original = tk.PhotoImage(master=master, data=payload, format="png")
    expected = struct.unpack_from(">II", payload, 16)
    if (original.width(), original.height()) != expected:
        raise RuntimeError("Brand image decoder returned unexpected dimensions")
    factor = max(1, math.ceil(max(original.width() / width, original.height() / height)))
    return original.subsample(factor, factor) if factor > 1 else original


def apply_window(window):
    window.configure(bg=BG)
    window.option_add("*Button.Background", PANEL)
    window.option_add("*Button.Foreground", TEXT)
    window.option_add("*Button.ActiveBackground", BORDER)
    window.option_add("*Button.ActiveForeground", TEXT)
    window.option_add("*Button.DisabledForeground", MUTED)
    window.option_add("*Button.Relief", "flat")
    window.option_add("*Button.Font", "{Segoe UI} 10")
    window.option_add("*Spinbox.Background", PANEL)
    window.option_add("*Spinbox.Foreground", TEXT)
    icon = icon_image(window)
    if icon is not None:
        window.iconphoto(True, icon)
        window._brand_icon = icon
    if os.name == "nt" and ICON.is_file():
        window.iconbitmap(default=str(ICON))


def brand_header(parent, compact=False):
    frame = tk.Frame(parent, bg=BG, padx=28, pady=16 if compact else 22)
    frame.pack(fill="x")
    image = logo_image(parent, width=420 if compact else 700, height=180 if compact else 320)
    if image is not None:
        picture = tk.Label(frame, image=image, bg=BG, borderwidth=0)
        picture.image = image
        picture.pack()
    else:
        tk.Label(frame, text="DekuForge", bg=BG, fg=GOLD,
                 font=("Segoe UI", 30, "bold")).pack()
    tk.Label(frame, text="Reforging a legend.", bg=BG, fg=GOLD,
             font=("Segoe UI", 12 if compact else 17)).pack(pady=(8, 0))
    return frame
