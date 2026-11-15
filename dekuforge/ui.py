"""One-window desktop navigation with a persistent three-step build workflow."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from queue import Empty, Queue
import threading
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from . import __version__
from .core import ROOT, launch, load_settings, save_installation, update_settings
from .engine import build_independent
from .i18n import LANGUAGES, MESSAGES, translate
from .native import prepare_archive
from .theme import BG, BORDER, GOLD, LEAF, MUTED, PANEL, TEXT, ArtworkLabel, BackgroundCanvas, apply_identity, apply_window, logo_image
from .workflow import BuildRequest, Progress, duration, validate_destination, validate_source


class Launcher:
    def __init__(self, root):
        self.root = root
        root.title("DekuForge")
        root.geometry("1120x760")
        root.minsize(960, 700)
        apply_window(root)
        root.protocol("WM_DELETE_WINDOW", self.close)
        settings = load_settings()
        self.language = settings.get("language", "nl")
        if self.language not in LANGUAGES:
            self.language = "nl"
        self.executable = settings.get("executable", "")
        self.source = settings.get("nup", "")
        self.destination = settings.get("build_destination", str(ROOT / "build" / "game"))
        self.hide_playing = settings.get("hide_playing", True) is True
        self.page, self.step = "home", 0
        self.process = None
        self.events = Queue()
        self.progress = Progress()
        self.result = None
        self.error = ""
        self.activity = ""
        self.log_lines = []
        self.log_path = None
        self.log_widget = None
        self.progressbar = None
        self.time_label = None
        self.phase_label = None
        self.last_log_length = 0
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.sidebar = tk.Frame(root, bg="#0d1c12", width=240)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.backdrop = BackgroundCanvas(root)
        self.backdrop.grid(row=0, column=1, sticky="nsew")
        self.backdrop.grid_rowconfigure(0, weight=1)
        self.backdrop.grid_columnconfigure(0, weight=1)
        self.content = BackgroundCanvas(self.backdrop, surface=self.backdrop)
        self.content.grid(row=0, column=0, sticky="nsew", padx=34, pady=28)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Forge.Horizontal.TProgressbar", troughcolor=PANEL, background=GOLD,
                        bordercolor=BORDER, lightcolor=GOLD, darkcolor=GOLD)
        style.configure("Forge.TCombobox", fieldbackground=PANEL, background=BORDER,
                        foreground=TEXT, arrowcolor=GOLD, padding=9)
        style.map("Forge.TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])
        self.render_navigation()
        self.render()
        root.after(100, self.tick)

    def t(self, key, **values):
        return translate(self.language, key, **values)

    def label(self, parent, text, size=11, color=TEXT, **options):
        widget = (ArtworkLabel(parent, text, size, color, **options) if isinstance(parent, BackgroundCanvas)
                  else tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                                font=("Segoe UI", size), justify="left", anchor="w", **options))
        if "wraplength" in options:
            maximum = options["wraplength"]
            def wrap(event):
                if widget.winfo_exists():
                    padding = int(parent.cget("padx")) if "padx" in parent.keys() else 0
                    widget.configure(wraplength=max(200, min(maximum, event.width - 2 * padding - 6)))
            parent.bind("<Configure>", wrap, add="+")
        return widget

    def button(self, parent, text, command, primary=False, **options):
        return tk.Button(parent, text=text, command=command, bg=GOLD if primary else BORDER,
                         fg=BG if primary else TEXT, activebackground=LEAF, activeforeground=BG,
                         font=("Segoe UI", 11, "bold" if primary else "normal"),
                         relief="flat", borderwidth=0, padx=18, pady=11, cursor="hand2", **options)

    def card(self, parent, padding=22):
        outer = BackgroundCanvas(parent, surface=self.backdrop, opacity=0.15)
        outer.configure(highlightbackground=BORDER, highlightthickness=1)
        outer.pack(fill="x", pady=(0, 16))
        frame = BackgroundCanvas(outer, surface=self.backdrop, opacity=0.15)
        frame.pack(fill="both", expand=True, padx=padding, pady=padding)
        return frame

    def render_navigation(self):
        for child in self.sidebar.winfo_children():
            child.destroy()
        image = logo_image(self.root, width=210, height=120)
        if image is not None:
            mark = tk.Label(self.sidebar, image=image, bg="#0d1c12")
            mark.image = image
            mark.pack(padx=14, pady=(32, 6))
        else:
            self.label(self.sidebar, "DekuForge", 22, GOLD).pack(padx=20, pady=30)
        self.label(self.sidebar, self.t("tagline"), 10, MUTED).pack(padx=22, pady=(0, 32))
        for name in ("home", "build", "settings"):
            selected = self.page == name
            self.button(self.sidebar, self.t(name), lambda value=name: self.navigate(value),
                        primary=selected, anchor="w").pack(fill="x", padx=16, pady=5)
        self.label(self.sidebar, f"{self.t('development')}\n{__version__}", 9, MUTED).pack(side="bottom", padx=22, pady=24)

    def navigate(self, page):
        self.page = page
        self.render_navigation()
        self.render()

    def render(self):
        if self.progressbar is not None:
            self.progressbar.stop()
        self.log_widget = self.progressbar = self.time_label = self.phase_label = None
        for child in self.content.winfo_children():
            child.destroy()
        self.label(self.content, self.t(self.page), 27, GOLD).pack(anchor="w", pady=(0, 20))
        if self.page == "home":
            self.render_home()
        elif self.page == "settings":
            self.render_settings()
        else:
            self.render_build()
        self.backdrop._schedule_resize(None)

    def render_home(self):
        self.label(self.content, self.t("welcome"), 20).pack(anchor="w", pady=(0, 6))
        self.label(self.content, self.t("welcome_help"), 11, MUTED, wraplength=650).pack(anchor="w", pady=(0, 28))
        card = self.card(self.content)
        self.label(card, self.t("installation").upper(), 10, LEAF).pack(anchor="w")
        selected = bool(self.executable and Path(self.executable).is_file())
        self.label(card, str(Path(self.executable).parent) if selected else self.t("no_install"),
                   12, TEXT, wraplength=620).pack(anchor="w", pady=(12, 18))
        row = BackgroundCanvas(card, surface=self.backdrop, opacity=0.15)
        row.pack(fill="x")
        running = self.process is not None and self.process.poll() is None
        self.button(row, self.t("playing") if running else "▶  " + self.t("play"), self.play,
                    primary=True, state="normal" if selected and not running else "disabled").pack(side="left")
        self.button(row, self.t("choose_install"), self.choose_installation).pack(side="left", padx=10)
        self.label(card, self.activity or self.t("ready" if selected else "not_ready"), 10, MUTED,
                   wraplength=620).pack(anchor="w", pady=(16, 0))
        next_card = self.card(self.content)
        self.label(next_card, self.t("build"), 17).pack(anchor="w")
        self.label(next_card, self.t("build_help"), 11, MUTED, wraplength=620).pack(anchor="w", pady=(7, 15))
        self.button(next_card, self.t("build") + "  →", lambda: self.navigate("build")).pack(anchor="w")
        if selected:
            self.button(self.content, self.t("open_folder"), lambda: self.open_folder(Path(self.executable).parent)).pack(anchor="w")

    def render_settings(self):
        card = self.card(self.content)
        self.label(card, self.t("language"), 16).pack(anchor="w")
        self.label(card, self.t("language_help"), 11, MUTED, wraplength=620).pack(anchor="w", pady=(6, 18))
        value = tk.StringVar(value=LANGUAGES[self.language])
        combo = ttk.Combobox(card, values=list(LANGUAGES.values()), textvariable=value,
                             state="readonly", style="Forge.TCombobox", font=("Segoe UI", 12), width=24)
        combo.pack(anchor="w")

        def change(_):
            self.set_language(next(code for code, title in LANGUAGES.items() if title == value.get()))
        combo.bind("<<ComboboxSelected>>", change)
        options = self.card(self.content)
        self.label(options, self.t("hide"), 14, wraplength=610).pack(anchor="w", pady=(0, 14))
        self.button(options, self.t("on" if self.hide_playing else "off"), self.toggle_hide,
                    primary=self.hide_playing).pack(anchor="w")
        self.button(self.content, self.t("open_log"), lambda: self.open_folder(ROOT / "local" / "logs")).pack(anchor="w", pady=8)
        self.label(self.content, self.t("about"), 10, MUTED, wraplength=630).pack(anchor="w", pady=20)

    def set_language(self, code):
        if code not in LANGUAGES:
            return
        self.persist({"language": code})
        self.language = code
        self.render_navigation()
        self.render()

    def toggle_hide(self):
        self.hide_playing = not self.hide_playing
        self.persist({"hide_playing": self.hide_playing})
        self.render()

    def render_build(self):
        steps = BackgroundCanvas(self.content, surface=self.backdrop)
        steps.pack(fill="x", pady=(0, 22))
        for index, key in enumerate(("source_step", "destination_step", "progress_step")):
            self.label(steps, self.t(key), 11, GOLD if self.step == index else MUTED).pack(side="left", padx=(0, 22))
        if self.step == 0:
            self.label(self.content, self.t("source_title"), 20).pack(anchor="w")
            self.label(self.content, self.t("source_help"), 11, MUTED, wraplength=650).pack(anchor="w", pady=(9, 22))
            card = self.card(self.content)
            self.path_row(card, self.t("source"), self.source, self.choose_source)
            self.button(self.content, self.t("next") + "  →", self.next_step, primary=True).pack(anchor="e", pady=12)
        elif self.step == 1:
            self.label(self.content, self.t("destination_title"), 20, wraplength=650).pack(anchor="w")
            self.label(self.content, self.t("destination_help"), 11, MUTED, wraplength=650).pack(anchor="w", pady=(9, 22))
            card = self.card(self.content)
            self.path_row(card, self.t("destination"), self.destination, self.choose_destination)
            row = BackgroundCanvas(self.content, surface=self.backdrop)
            row.pack(fill="x", pady=12)
            self.button(row, self.t("back"), lambda: self.set_step(0)).pack(side="left")
            self.button(row, self.t("review") + "  →", self.next_step, primary=True).pack(side="right")
        else:
            self.render_progress()

    def path_row(self, parent, title, path, command):
        self.label(parent, title.upper(), 10, LEAF).pack(anchor="w")
        self.label(parent, path or "—", 11, TEXT, wraplength=610).pack(anchor="w", pady=12)
        self.button(parent, self.t("browse"), command).pack(anchor="w")

    def render_progress(self):
        self.label(self.content, self.t("build_title"), 20).pack(anchor="w", pady=(0, 12))
        summary = self.card(self.content, padding=16)
        self.label(summary, Path(self.source).name, 12).pack(anchor="w")
        self.label(summary, self.destination, 10, MUTED, wraplength=640).pack(anchor="w", pady=(5, 0))
        self.phase_label = self.label(self.content, "", 12, LEAF, wraplength=650)
        self.phase_label.pack(anchor="w", pady=(0, 8))
        self.progressbar = ttk.Progressbar(self.content, mode="indeterminate", style="Forge.Horizontal.TProgressbar")
        self.progressbar.pack(fill="x", pady=(0, 8))
        self.time_label = self.label(self.content, "", 10, MUTED)
        self.time_label.pack(anchor="w", pady=(0, 12))
        if self.progress.active:
            self.progressbar.start(18)
        elif not self.error and self.result is None:
            self.label(self.content, self.t("engine_pending"), 10, GOLD, wraplength=650).pack(anchor="w", pady=(0, 12))
        self.label(self.content, self.t("logs"), 11).pack(anchor="w", pady=(0, 6))
        self.log_widget = ScrolledText(self.content, bg="#0a1710", fg=TEXT, relief="flat", borderwidth=0,
                                       insertbackground=GOLD, font=("Consolas", 9), height=7, state="normal")
        self.log_widget.pack(fill="both", expand=True)
        self.log_widget.insert("end", "".join(self.log_lines[-700:]))
        self.log_widget.configure(state="disabled")
        self.last_log_length = len(self.log_lines)
        row = tk.Frame(self.content, bg=BG)
        row.pack(fill="x", pady=(14, 0))
        if not self.progress.active:
            if self.result:
                self.button(row, self.t("use_build"), self.use_result, primary=True).pack(side="right")
            elif self.error:
                self.button(row, self.t("new_build"), self.reset_build, primary=True).pack(side="right")
                self.button(row, self.t("open_log"), lambda: self.open_folder(ROOT / "local" / "logs")).pack(side="left")
            else:
                self.button(row, self.t("start_build"), self.start_build, primary=True).pack(side="right")
                self.button(row, self.t("back"), lambda: self.set_step(1)).pack(side="left")
        self.refresh_progress()

    def persist(self, changes):
        try:
            update_settings(changes)
        except OSError as error:
            self.show_error(error)
            raise

    def show_error(self, error):
        text = self.t(str(error)) if str(error) in MESSAGES["en"] else str(error)
        messagebox.showerror(self.t("error"), text, parent=self.root)

    def choose_installation(self):
        value = filedialog.askopenfilename(parent=self.root, title=self.t("select_exe"), filetypes=[(self.t("game_file"), "*.exe"), (self.t("all_files"), "*")])
        if value:
            try:
                self.executable = str(save_installation(value))
                self.activity = ""
                self.render()
            except (OSError, ValueError) as error:
                self.show_error(error)

    def choose_source(self):
        value = filedialog.askopenfilename(parent=self.root, title=self.t("source_title"),
                                           filetypes=[("NUP / ROM", "*.nup *.rom *.z64 *.n64 *.v64"), (self.t("all_files"), "*")])
        if value:
            try:
                self.source = str(validate_source(value))
                self.persist({"nup": self.source})
                self.render()
            except (OSError, ValueError) as error:
                self.show_error(error)

    def choose_destination(self):
        value = filedialog.askdirectory(parent=self.root, title=self.t("destination_title"), mustexist=False,
                                        initialdir=str(Path(self.destination).parent))
        if value:
            try:
                self.destination = str(validate_destination(value, self.executable))
                self.persist({"build_destination": self.destination})
                self.render()
            except (OSError, ValueError) as error:
                self.show_error(error)

    def next_step(self):
        try:
            validate_source(self.source)
            if self.step == 1:
                validate_destination(self.destination, self.executable)
            self.set_step(min(2, self.step + 1))
        except (OSError, ValueError) as error:
            self.show_error(error)

    def set_step(self, step):
        if self.progress.active:
            return
        self.step = step
        self.render()

    def play(self):
        if self.process is not None and self.process.poll() is None:
            return
        try:
            self.process = launch(self.executable)
            self.activity = self.t("playing")
            self.render()
            if self.hide_playing:
                self.root.withdraw()
        except (OSError, ValueError) as error:
            self.show_error(error)

    def start_build(self):
        if self.progress.active:
            return
        try:
            request = BuildRequest.create(self.source, self.destination, self.executable)
            folder = ROOT / "local" / "logs"
            folder.mkdir(parents=True, exist_ok=True)
            self.log_path = folder / ("build-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".log")
            self.log_path.touch(exist_ok=False)
        except (OSError, ValueError) as error:
            self.show_error(error)
            return
        self.error, self.result, self.log_lines = "", None, []
        self.progress.begin()
        self.render()

        def worker():
            def notify(kind, value):
                self.events.put((kind, value))
            try:
                with self.log_path.open("a", encoding="utf-8") as output:
                    def logged(kind, value):
                        output.write(f"[{kind}] {value}\n")
                        output.flush()
                        notify(kind, value)
                    executable = build_independent(request.source, logged, destination=request.destination)
                    if executable is None or not Path(executable).is_file():
                        raise RuntimeError("The build did not produce a playable executable")
                    notify("success", str(executable))
            except Exception as error:
                try:
                    with self.log_path.open("a", encoding="utf-8") as output:
                        output.write(f"[error] {error}\n")
                except OSError:
                    pass
                notify("failure", str(error))
            finally:
                notify("done", None)
        threading.Thread(target=worker, daemon=False).start()

    def refresh_progress(self):
        if self.time_label is None:
            return
        remaining = self.progress.remaining()
        estimate = (duration(remaining) if remaining is not None else self.t("estimating")) if self.progress.active else "—"
        self.time_label.configure(text=self.t("elapsed", time=duration(self.progress.elapsed())) +
                                  "   ·   " + self.t("remaining", time=estimate))
        key = "working" if self.progress.active else "failed" if self.error else "finished" if self.result else "not_started"
        phase = self.progress.phase
        phase = {"module": "prepared", "extract": "prepared"}.get(phase, phase)
        stage = self.t(phase) if phase in MESSAGES["en"] else phase
        self.phase_label.configure(text=self.t(key) + (" · " + stage if self.progress.active else ""))
        if self.result:
            self.progressbar.configure(mode="determinate", value=100)
        if self.progress.total and self.progress.done and self.progress.active:
            self.progressbar.stop()
            self.progressbar.configure(mode="determinate", value=100 * self.progress.done / self.progress.total)
        elif self.progress.active and self.progressbar.cget("mode") != "indeterminate":
            self.progressbar.configure(mode="indeterminate")
            self.progressbar.start(18)
        if self.log_widget is not None and len(self.log_lines) > self.last_log_length:
            self.log_widget.configure(state="normal")
            for line in self.log_lines[self.last_log_length:]:
                self.log_widget.insert("end", line)
            self.last_log_length = len(self.log_lines)
            if int(self.log_widget.index("end-1c").split(".")[0]) > 900:
                self.log_widget.delete("1.0", "300.0")
            self.log_widget.see("end")
            self.log_widget.configure(state="disabled")

    def tick(self):
        changed = False
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except Empty:
                break
            if kind in ("progress", "phase"):
                self.progress.update(value)
            if kind in ("log", "checked", "failure"):
                self.log_lines.append(str(value).rstrip() + "\n")
            if kind == "success":
                self.result = value
            elif kind == "failure":
                self.error = value
            elif kind == "done":
                self.progress.finish()
                changed = True
        if len(self.log_lines) > 1600:
            self.log_lines = self.log_lines[-900:]
            self.last_log_length = 0
            if self.log_widget is not None:
                self.log_widget.configure(state="normal")
                self.log_widget.delete("1.0", "end")
                self.log_widget.configure(state="disabled")
        if self.process is not None and self.process.poll() is not None:
            self.activity = self.t("game_ended", code=self.process.returncode)
            self.process = None
            self.root.deiconify()
            changed = True
        if changed:
            self.render()
        self.refresh_progress()
        self.root.after(100, self.tick)

    def use_result(self):
        if self.result:
            try:
                self.executable = str(save_installation(self.result))
                self.navigate("home")
            except (OSError, ValueError) as error:
                self.show_error(error)

    def reset_build(self):
        if not self.progress.active:
            self.error, self.result, self.log_lines = "", None, []
            self.progress = Progress()
            self.step = 0
            self.render()

    def open_folder(self, folder):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(folder))
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as error:
            self.show_error(error)

    def close(self):
        if self.progress.active:
            messagebox.showinfo("DekuForge", self.t("active_build"), parent=self.root)
            return
        self.root.destroy()


def main():
    apply_identity()
    root = tk.Tk(className="DekuForge")
    root._launcher = Launcher(root)
    if "--self-test" in sys.argv:
        def self_test():
            application = root._launcher
            checked = []
            try:
                for language in LANGUAGES:
                    application.language = language
                    for page in ("home", "build", "settings"):
                        application.navigate(page)
                        root.update_idletasks()
                        checked.append(f"{language}/{page}")
                    for step in (1, 2):
                        application.step = step
                        application.navigate("build")
                        root.update_idletasks()
                        checked.append(f"{language}/build/{step}")
                    application.step = 0
                report = {"screens": checked, "logo_loaded": root._brand_icon.width() > 0,
                          "top_level_windows": 1 + sum(isinstance(child, tk.Toplevel) for child in root.winfo_children()),
                          "success": True}
            except Exception as error:
                report = {"screens": checked, "success": False, "error": str(error)}
            folder = ROOT / "local"
            folder.mkdir(exist_ok=True)
            (folder / "launcher-selftest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            root.destroy()
        root.after(100, self_test)
    root.mainloop()
