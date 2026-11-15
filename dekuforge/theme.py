"""Shared leaf-green and forged-gold desktop styling."""

import math
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


def logo_image(master, width=650, height=310):
    if not LOGO.is_file():
        return None
    original = tk.PhotoImage(master=master, file=str(LOGO))
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
    icon = logo_image(window, width=64, height=64)
    if icon is not None:
        window.iconphoto(True, icon)
        window._brand_icon = icon


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
