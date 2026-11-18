"""Shared leaf-green and forged-gold desktop styling."""

import math
from functools import lru_cache
import os
import struct
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText as NativeScrolledText

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


@lru_cache(maxsize=2)
def green_gradient(menu=False):
    """Small procedural texture, smoothly scaled to the client area."""
    from PIL import Image
    image = Image.new("RGB", (160, 160))
    pixels = []
    for y in range(160):
        for x in range(160):
            distance = ((x/159-.5)/.7)**2 + ((y/159-(.22 if menu else .5))/.8)**2
            glow = max(0, 1-distance)**2
            base, light = ((8, 17, 11), (30, 47, 27)) if menu else ((3, 10, 6), (15, 30, 19))
            pixels.append(tuple(round(a+(b-a)*glow) for a, b in zip(base, light)))
    image.putdata(pixels)
    return image


def rgb_photo(master, image):
    """Transfer pixels directly; PNG compression on every UI frame blocks Tk."""
    image = image.convert("RGB")
    header = f"P6\n{image.width} {image.height}\n255\n".encode("ascii")
    return tk.PhotoImage(master=master, data=header + image.tobytes(), format="PPM")


def style_controls(window):
    """Style both ttk fields and the separate Tk combobox popdown list."""
    style = ttk.Style(window)
    style.theme_use("clam")
    style.configure("Forge.TCombobox", fieldbackground=PANEL, background=BORDER,
                    foreground=TEXT, arrowcolor=GOLD, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, padding=9)
    style.map("Forge.TCombobox", fieldbackground=[("readonly", PANEL), ("disabled", BG)],
              foreground=[("disabled", MUTED), ("readonly", TEXT)],
              bordercolor=[("focus", GOLD), ("active", GOLD)],
              arrowcolor=[("disabled", MUTED), ("active", TEXT)],
              background=[("active", "#485e32")])
    for orientation in ("Vertical", "Horizontal"):
        style.configure(f"{orientation}.TScrollbar", background=BORDER, troughcolor=BG,
                        bordercolor=PANEL, arrowcolor=GOLD, lightcolor=BORDER, darkcolor=BORDER)
        style.map(f"{orientation}.TScrollbar", background=[("active", "#536b36")])
    for option, value in {"background": PANEL, "foreground": TEXT, "selectBackground": GOLD,
                          "selectForeground": BG, "font": "{Segoe UI} 12", "borderWidth": 0,
                          "highlightThickness": 1, "highlightColor": GOLD,
                          "highlightBackground": BORDER, "relief": "flat"}.items():
        window.option_add(f"*TCombobox*Listbox.{option}", value)
    window.option_add("*Listbox.selectBackground", GOLD)
    window.option_add("*Listbox.selectForeground", BG)
    window.option_add("*Text.selectBackground", GOLD)
    window.option_add("*Text.selectForeground", BG)


def button_feedback(button, primary=False):
    normal = GOLD if primary else BORDER
    hover = "#f5cf73" if primary else "#496136"
    state = {"hover": False, "focus": False}
    button.configure(activebackground=hover, activeforeground=BG if primary else TEXT,
                     highlightthickness=1, highlightbackground=normal, highlightcolor=GOLD)
    def update(key, value):
        state[key] = value
        active = any(state.values()) and str(button.cget("state")) != "disabled"
        button.configure(bg=hover if active else normal,
                         highlightbackground=GOLD if active else normal)
    for event, key, value in (("<Enter>", "hover", True), ("<Leave>", "hover", False),
                              ("<FocusIn>", "focus", True), ("<FocusOut>", "focus", False)):
        button.bind(event, lambda e, k=key, v=value: update(k, v), add="+")
    return button


def style_titlebar(window):
    """Keep native resizing, snapping and system controls with branded Win11 colors."""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    user = ctypes.WinDLL("user32")
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetAncestor.restype = wintypes.HWND
    try:
        dwm = ctypes.WinDLL("dwmapi")
    except OSError:
        return
    dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dwm.DwmSetWindowAttribute.restype = ctypes.c_long
    def apply(event=None):
        if event is not None and event.widget is not window:
            return
        hwnd = user.GetAncestor(window.winfo_id(), 2)
        for attribute, number in ((20, 1), (35, 0x121c0d), (36, 0x4fb9e8), (34, 0x284a34)):
            value = wintypes.DWORD(number)
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    window.bind("<Map>", apply, add="+")
    job = window.after_idle(apply)
    window.bind("<Destroy>", lambda e: window.after_cancel(job) if e.widget is window else None, add="+")


class BackgroundCanvas(tk.Canvas):
    """Static, darkened artwork behind normal, opaque interface controls."""

    def __init__(self, parent, *, surface=None, opacity=None, **options):
        super().__init__(parent, bg=BG, highlightthickness=0, borderwidth=0, **options)
        self._surface = surface
        self._opacity = opacity if opacity is not None else getattr(parent, "_opacity", .46) if surface is not None else .46
        self._art = None
        self._fitted = None
        self._image = None
        self._resize_job = None
        self._draw_key = None
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
        owner = self._surface or self
        key = (self.winfo_width(), self.winfo_height(), owner.winfo_width(), owner.winfo_height(),
               self.winfo_rootx()-owner.winfo_rootx(), self.winfo_rooty()-owner.winfo_rooty(),
               self._opacity, getattr(self, "reveal", None), id(owner._art))
        if key == self._draw_key:
            return
        subdued = self._region()
        if subdued is None:
            return
        self._image = rgb_photo(self, subdued)
        self._draw_key = key
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
        # PhotoImage finalizers call Tk; release this on the UI thread.
        self._image = None


class NavigationCanvas(BackgroundCanvas):
    def __init__(self, parent, **options):
        super().__init__(parent, opacity=1, **options)
        self._art = green_gradient(menu=True)


class PagePanel(tk.Frame):
    """One padded artwork panel with overflow scrolling and focus visibility."""
    def __init__(self, parent, surface, padding=28):
        super().__init__(parent, bg=BORDER, highlightthickness=0, borderwidth=0)
        self.padding = padding
        self.viewport = BackgroundCanvas(self, surface=surface, opacity=.15)
        self.viewport.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        style = ttk.Style(self)
        style.layout("Forge.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
            "sticky":"ns", "children":[("Vertical.Scrollbar.thumb", {"expand":True,"sticky":"nswe"})]})])
        style.configure("Forge.Vertical.TScrollbar", width=9, background=BORDER,
                        troughcolor=BG, borderwidth=0, gripcount=0)
        style.map("Forge.Vertical.TScrollbar", background=[("active", GOLD), ("pressed", GOLD)])
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.viewport.yview,
                                    style="Forge.Vertical.TScrollbar")
        self.viewport.configure(yscrollcommand=self._scrolled, yscrollincrement=24)
        self.body = BackgroundCanvas(self.viewport, surface=surface, opacity=.15)
        self._window = self.viewport.create_window(padding, padding, window=self.body, anchor="nw")
        self.viewport.bind("<Configure>", self._resize, add="+")
        self.body.bind("<Configure>", self._body_changed, add="+")
        self._event_root = self.winfo_toplevel()
        self._wheel = self._event_root.bind("<MouseWheel>", self._mousewheel, add="+")
        self._focus = self._event_root.bind("<FocusIn>", self._focus_changed, add="+")

    def _resize(self, event):
        self.viewport.itemconfigure(self._window, width=max(1, event.width-2*self.padding))
        self._body_changed()

    def _body_changed(self, _event=None):
        self.viewport.configure(scrollregion=(0, 0, self.viewport.winfo_width(),
                                              self.body.winfo_reqheight()+2*self.padding))

    def _scrolled(self, first, last):
        self.scroll.set(first, last)
        needed = float(first) > 0 or float(last) < 1
        if needed and not self.scroll.winfo_manager():
            self.scroll.pack(side="right", fill="y", padx=(0,1), pady=6)
        elif not needed and self.scroll.winfo_manager():
            self.scroll.pack_forget()

    def _contains(self, widget):
        return widget is self.body or widget is not None and str(widget).startswith(str(self.body)+".")

    def _mousewheel(self, event):
        if (event.widget is not self.viewport and not self._contains(event.widget)) or isinstance(event.widget, (tk.Text, tk.Listbox, ttk.Combobox)):
            return
        if self.scroll.winfo_manager():
            self.viewport.yview_scroll(-int(event.delta/120) or (-1 if event.delta>0 else 1), "units")
            return "break"

    def reveal(self, widget):
        """Scroll a keyboard-focused action into view without moving the backdrop."""
        self.update_idletasks()
        top = widget.winfo_rooty()-self.viewport.winfo_rooty()
        bottom = top+widget.winfo_height()
        height = self.viewport.winfo_height()
        shift = top-12 if top < 12 else bottom-height+12 if bottom > height-12 else 0
        if shift:
            total = self.body.winfo_reqheight()+2*self.padding
            self.viewport.yview_moveto((self.viewport.canvasy(0)+shift)/max(1,total))

    def _focus_changed(self, event):
        if self._contains(event.widget):
            self.reveal(event.widget)

    def destroy(self):
        self._event_root.unbind("<MouseWheel>", self._wheel)
        self._event_root.unbind("<FocusIn>", self._focus)
        super().destroy()


class ScrolledText(NativeScrolledText):
    """Text editor/log view with the same narrow scrollbar as page panels."""
    def __init__(self, parent, **options):
        super().__init__(parent, **options)
        self.frame.configure(bg=PANEL)
        self.vbar.destroy()
        self.vbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.yview,
                                  style="Forge.Vertical.TScrollbar")
        self.vbar.pack(side="right", fill="y", padx=(6,0))
        self.configure(yscrollcommand=self.vbar.set)


class NavigationLogo(BackgroundCanvas):
    """Transparent logo above the navigation's matching gradient region."""
    def __init__(self, parent, image):
        super().__init__(parent, surface=parent, opacity=1, width=image.width(), height=image.height())
        self.image = image
        self._logo = self.create_image(0, 0, image=image, anchor="nw")

    def configure(self, cnf=None, **options):
        if "image" in options:
            self.itemconfigure(self._logo, image=options.pop("image"))
        return super().configure(cnf, **options)

    def cget(self, key):
        if key == "image":
            return self.itemcget(self._logo, "image")
        return super().cget(key)


    def destroy(self):
        super().destroy()
        self.image = None


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
    cache = getattr(master, "_brand_images", None)
    if cache is None:
        master._brand_images = cache = {}
    key = (str(path), path.stat().st_mtime_ns, width, height)
    if key in cache:
        return cache[key]
    payload = path.read_bytes()
    original = tk.PhotoImage(master=master, data=payload, format="png")
    expected = struct.unpack_from(">II", payload, 16)
    if (original.width(), original.height()) != expected:
        raise RuntimeError("Brand image decoder returned unexpected dimensions")
    factor = max(1, math.ceil(max(original.width() / width, original.height() / height)))
    result = original.subsample(factor, factor) if factor > 1 else original
    cache[key] = result
    return result


def apply_window(window):
    window.configure(bg=BG)
    style_controls(window)
    style_titlebar(window)
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
        window.iconbitmap(str(ICON))
        window.iconbitmap(default=str(ICON))
        from .window_icon import install
        install(window, ICON)


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
