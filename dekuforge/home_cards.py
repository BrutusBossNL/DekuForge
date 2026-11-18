"""Responsive artwork actions with pointer and keyboard feedback."""
from io import BytesIO
from pathlib import Path
import tkinter as tk

from .theme import BG, BORDER, GOLD, MUTED, PANEL, TEXT, BackgroundCanvas, green_gradient, rgb_photo


class StartupCanvas(BackgroundCanvas):
    def __init__(self, parent):
        super().__init__(parent, opacity=1)
        self.reveal = 0
        self.gradient = green_gradient()

    def _region(self):
        from PIL import Image
        art = super()._region()
        size = (max(1, self.winfo_width()), max(1, self.winfo_height()))
        gradient = self.gradient.resize(size, Image.Resampling.BILINEAR)
        return Image.blend(gradient, art, self.reveal) if art is not None else gradient

    def destroy(self):
        if hasattr(self, '_logo_frames'):
            self._logo_frames.clear()
        super().destroy()


class ActionCard(tk.Canvas):
    def __init__(self, parent, artwork, title, detail, command, enabled=True, badge="", badge_color=GOLD):
        super().__init__(parent, background=PANEL, highlightthickness=3,
                         highlightbackground=BORDER, highlightcolor=GOLD,
                         takefocus=True, cursor="hand2" if enabled else "arrow")
        self.title, self.detail, self.command = title, detail, command
        self.enabled = enabled
        self.badge, self.badge_color = badge, badge_color
        self.hovered = self.focused = False
        self.artwork = None
        self.images = {}
        self.image = None
        self.resize_job = None
        if Path(artwork).is_file():
            from PIL import Image
            with Image.open(artwork) as source:
                self.artwork = source.convert("RGB")
        self.bind("<Configure>", self.schedule)
        self.bind("<Enter>", lambda e: self.highlight(hovered=True))
        self.bind("<Leave>", lambda e: self.highlight(hovered=False))
        self.bind("<FocusIn>", lambda e: self.highlight(focused=True))
        self.bind("<FocusOut>", lambda e: self.highlight(focused=False))
        self.bind("<Button-1>", self.activate)
        self.bind("<Return>", self.activate)
        self.bind("<space>", self.activate)

    def activate(self, _event=None):
        self.focus_set()
        if self.enabled:
            self.command()
        return "break"

    def highlight(self, **state):
        for key, value in state.items():
            setattr(self, key, value)
        self.draw()

    def schedule(self, _event=None):
        if self.resize_job:
            self.after_cancel(self.resize_job)
        self.resize_job = self.after(35, self.draw)

    def draw(self):
        if self.resize_job:
            self.after_cancel(self.resize_job)
            self.resize_job = None
        active = self.hovered or self.focused
        self.configure(highlightbackground=GOLD if active else BORDER,
                       background="#34412a" if active else PANEL)
        self.delete("content")
        width, height = self.winfo_width() - 6, self.winfo_height() - 6
        if width < 10 or height < 10:
            return
        art_height = max(20, height - 114)
        if self.artwork:
            from PIL import Image, ImageOps, ImageEnhance
            size = (width, art_height)
            if self.images.get("size") != size:
                fitted = ImageOps.fit(self.artwork, size, method=Image.Resampling.LANCZOS,
                                      centering=(0.5, 0.35))
                self.images = {"size": size}
                for name, brightness in (("idle", .83 if self.enabled else .48), ("active", 1.08 if self.enabled else .65)):
                    self.images[name] = rgb_photo(self, ImageEnhance.Brightness(fitted).enhance(brightness))
            self.image = self.images["active" if active else "idle"]
            self.create_image(3, 3, image=self.image, anchor="nw", tags="content")
        self.create_text(width / 2 + 3, art_height + 18, text=self.title,
                         fill=GOLD if active else TEXT, font=("Segoe UI", 17, "bold"),
                         anchor="n", width=width - 18, justify="center", tags="content")
        detail = self.detail
        # Preserve both ends of long paths; the full path remains in Settings.
        if len(detail) > 100:
            detail = detail[:25] + " … " + detail[-65:]
        self.create_text(width / 2 + 3, art_height + 57, text=detail, fill=TEXT if active else MUTED,
                         font=("Segoe UI", 9), anchor="n", width=width - 22,
                         justify="center", tags="content")
        if self.badge:
            self.create_text(width / 2 + 3, art_height + 87, text=self.badge, fill=self.badge_color,
                             font=("Segoe UI", 10, "bold"), anchor="n", tags="content")

    def destroy(self):
        if self.resize_job:
            self.after_cancel(self.resize_job)
        super().destroy()
        self.images.clear()
        self.image = None


def animate_intro(app):
    """Move a single, unfaded logo from the padded top into the navigation."""
    from .theme import BackgroundCanvas, LOGO
    from PIL import Image
    root = app.root
    app.cancel_intro()
    root.update_idletasks()
    mark = getattr(app, "logo_label", None)
    logo_frames = []
    if mark is not None and LOGO.is_file():
        width, height = mark.image.width(), mark.image.height()
        # The root is intentionally withdrawn here. Absolute screen coordinates
        # are not valid until mapping; the navigation has a fixed 240px column.
        target = (120, 32 + height / 2)
        with Image.open(LOGO) as source:
            for step in range(13):
                scale = 1 + .35 * (1 - step / 12)**3
                resized = source.convert("RGBA").resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)
                payload = BytesIO()
                resized.save(payload, format="PNG")
                logo_frames.append(tk.PhotoImage(master=root, data=payload.getvalue(), format="png"))
        mark._intro_blank = tk.PhotoImage(master=root, width=width, height=height)
        mark.configure(image=mark._intro_blank)
    cover = StartupCanvas(root)
    cover.place(x=0, y=0, relwidth=1, relheight=1)
    tk.Misc.lift(cover)
    app.intro_cover = cover
    app.intro_job = None
    logo_item = cover.create_image(root.winfo_width()/2, 32 + logo_frames[0].height()/2,
                                   image=logo_frames[0], state="hidden") if logo_frames else None
    cover._logo_frames = logo_frames  # Retain image bytes throughout the animation.
    sidebar_item = None
    root.update_idletasks()
    cover._redraw()  # Paint the dark gradient before the root is first shown.

    def frame(step=-8):
        nonlocal sidebar_item
        app.intro_job = None
        center = (root.winfo_width()/2, 32 + logo_frames[-1].height()/2) if logo_frames else (0, 0)
        if step < 0:
            cover.reveal = (step + 8) / 8
            cover._redraw()
        elif step <= 12:
            cover.reveal = 1
            cover._opacity = 1 - .54 * step / 12
            cover._redraw()
            if logo_item is not None:
                cover.coords(logo_item, root.winfo_width()/2, 32 + logo_frames[step].height()/2)
                cover.itemconfigure(logo_item, image=logo_frames[step])
                cover.itemconfigure(logo_item, state="normal")
        elif step <= 25:
            if step == 13:
                app.sidebar.grid_remove()
                sidebar_item = cover.create_window(-240, 0, window=app.sidebar, anchor="nw",
                                                   width=240, height=root.winfo_height())
            t = (step - 13) / 12
            ease = 1 - (1-t)**3
            cover.coords(sidebar_item, -240 * (1-ease), 0)
            if logo_item is not None:
                cover.coords(logo_item, center[0] + (target[0]-center[0])*ease,
                             center[1] + (target[1]-center[1])*ease)
                cover.tag_raise(logo_item)
        else:
            app.cancel_intro()
            app.animate_cards()
            return
        app.intro_job = root.after(35, lambda: frame(step + 1))
    app.intro_job = root.after(180, frame)
