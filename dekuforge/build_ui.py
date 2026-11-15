"""Responsive build window; subprocess output reaches Tk through a queue."""

import os
from queue import Empty, Queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from .builder import default_backend, run_build, validate_nup
from .core import load_settings, save_installation, update_settings
from .native import prepare_archive
from .gameplan import prepare_game
from .engine import build_independent
from .theme import BG, PANEL, LEAF, GOLD, TEXT, apply_window, brand_header


def open_builder(parent, on_installation):
    window = tk.Toplevel(parent)
    window.title("DekuForge — Game bouwen")
    window.geometry("980x850")
    window.minsize(900, 800)
    apply_window(window)
    settings = load_settings()
    nup = tk.StringVar(value=settings.get("nup", ""))
    backend = tk.StringVar(value=settings.get("backend", str(default_backend())))
    status = tk.StringVar(value="NUP kiezen, controleren en daarna bouwen naar DekuForge/build/game.")
    workers = tk.IntVar(value=min(4, os.cpu_count() or 1))
    events = Queue()
    active = False
    built = None

    def row(title, value, chooser):
        frame = tk.Frame(window, bg=BG)
        frame.pack(fill="x", padx=24, pady=7)
        tk.Label(frame, text=title, bg=BG, fg=TEXT, width=18, anchor="w").pack(side="left")
        tk.Entry(frame, textvariable=value, state="readonly", readonlybackground=PANEL, fg=TEXT).pack(side="left", fill="x", expand=True, ipady=7)
        tk.Button(frame, text="Kiezen", command=chooser).pack(side="left", padx=(8, 0))

    def choose_nup():
        value = filedialog.askopenfilename(parent=window, title="Kies je eigen NUP", filetypes=[("NUP-bestand", "*.nup")])
        if value:
            try:
                nup.set(str(validate_nup(value)))
                update_settings({"nup": nup.get()})
            except (OSError, ValueError) as error:
                messagebox.showerror("NUP kiezen", str(error), parent=window)

    def choose_backend():
        value = filedialog.askdirectory(parent=window, title="Kies een compatibiliteitsinstallatie (met app, python en toolchain)")
        if value:
            backend.set(value)

    def begin(mode):
        nonlocal active, built
        if active:
            return
        try:
            validate_nup(nup.get())
            jobs = workers.get()
            update_settings({"nup": nup.get(), "backend": backend.get()})
        except (OSError, ValueError, tk.TclError) as error:
            messagebox.showerror("Game bouwen", str(error), parent=window)
            return
        values = (nup.get(), backend.get(), jobs)
        active = True
        built = None
        use_button.configure(state="disabled")
        check_button.configure(state="disabled")
        build_button.configure(state="disabled")
        extract_button.configure(state="disabled")
        status.set("DekuForge verwerkt je archief...")

        def worker():
            try:
                emit = lambda kind, data: events.put((kind, data))
                if mode == "compat":
                    run_build(values[0], values[1], emit, jobs=values[2])
                elif mode == "build":
                    build_independent(values[0], emit)
                elif mode == "prepare":
                    prepare_game(values[0], emit)
                else:
                    prepare_archive(values[0], emit, extract=mode == "extract")
            except Exception as error:
                events.put(("error", str(error)))
            finally:
                events.put(("finished", None))

        threading.Thread(target=worker, daemon=False).start()

    def use_build():
        if built:
            try:
                value = str(save_installation(built))
                on_installation(value)
                status.set("Nieuwe build gekoppeld. Saves zijn niet automatisch overgezet.")
            except (OSError, ValueError) as error:
                messagebox.showerror("Build koppelen", str(error), parent=window)

    def drain():
        nonlocal active, built
        # Bound work per tick so a verbose compiler cannot starve the window.
        for _ in range(150):
            try:
                kind, data = events.get_nowait()
            except Empty:
                break
            if kind == "log":
                log.insert("end", data)
                log.see("end")
                if int(log.index("end-1c").split(".")[0]) > 1500:
                    log.delete("1.0", "500.0")
            elif kind == "progress":
                status.set(json_progress(data))
            elif kind == "built":
                built = data
                status.set("Build gereed. Koppel hem expliciet met 'Deze build gebruiken'.")
                use_button.configure(state="normal")
            elif kind in ("checked", "error"):
                status.set(data)
                log.insert("end", data + "\n")
                log.see("end")
            elif kind == "finished":
                active = False
                check_button.configure(state="normal")
                build_button.configure(state="normal")
                extract_button.configure(state="normal")
        window.after(100, drain)

    def close():
        if active:
            messagebox.showinfo("Build actief", "Laat de build afronden voordat je de launcher sluit.", parent=window)
        else:
            window.destroy()

    brand_header(window, compact=True)
    tk.Label(window, text="NUP / GAME BUILDER", bg=BG, fg=GOLD, font=("Segoe UI", 16)).pack(anchor="w", padx=24, pady=(4, 6))
    tk.Label(window, text="Eigen NUP-verwerking en meegeleverde enginebron. De zelfstandige gameport is nog in ontwikkeling.",
             bg=BG, fg=TEXT, wraplength=850, justify="left").pack(anchor="w", padx=24, pady=5)
    row("Eigen NUP-bestand", nup, choose_nup)
    row("Compatibiliteitsmap", backend, choose_backend)
    actions = tk.Frame(window, bg=BG)
    actions.pack(fill="x", padx=24, pady=12)
    tk.Label(actions, text="Workers", bg=BG, fg=TEXT).pack(side="left")
    tk.Spinbox(actions, from_=1, to=os.cpu_count() or 1, textvariable=workers, width=4).pack(side="left", padx=8)
    check_button = tk.Button(actions, text="NUP controleren", command=lambda: begin("check"))
    check_button.pack(side="left", padx=6)
    extract_button = tk.Button(actions, text="Uitpakken", command=lambda: begin("extract"))
    extract_button.pack(side="left", padx=6)
    build_button = tk.Button(actions, text="Zelfstandig bouwen", command=lambda: begin("build"), bg=GOLD, fg=BG, activebackground=LEAF, activeforeground=BG)
    build_button.pack(side="left", padx=6)
    use_button = tk.Button(actions, text="Deze build gebruiken", command=use_build, state="disabled")
    use_button.pack(side="left", padx=6)
    advanced = tk.Frame(window, bg=BG)
    advanced.pack(fill="x", padx=24, pady=(0, 8))
    tk.Button(advanced, text="Alleen voorbereiden", command=lambda: begin("prepare")).pack(side="left", padx=6)
    tk.Button(advanced, text="Optionele compatibiliteitsbuild", command=lambda: begin("compat")).pack(side="left", padx=6)
    tk.Label(window, textvariable=status, bg=BG, fg=LEAF, wraplength=850, justify="left").pack(fill="x", padx=24, pady=8)
    log = ScrolledText(window, bg=PANEL, fg=TEXT, insertbackground=GOLD, font=("Consolas", 10), height=18)
    log.pack(fill="both", expand=True, padx=24, pady=(0, 20))
    window.protocol("WM_DELETE_WINDOW", close)
    # Prevent closing the root from orphaning an active build worker.
    window.transient(parent)
    window.grab_set()
    drain()
    return window, lambda: active


def json_progress(data):
    if isinstance(data, dict):
        return " | ".join(f"{key}: {value}" for key, value in data.items())[:650]
    return str(data)[:650]
