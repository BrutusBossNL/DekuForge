"""Forest and copper desktop launcher, written independently for DekuForge."""

import tkinter as tk
from tkinter import filedialog, messagebox
from . import __version__
from .core import launch, load_installation, save_installation
from .build_ui import open_builder

BG, PANEL, GREEN, COPPER, TEXT = "#101b17", "#1b2d25", "#b4d68b", "#db9d62", "#ecede3"


def main():
    root = tk.Tk()
    root.title("DekuForge — Reforging a legend.")
    root.geometry("900x590")
    root.minsize(760, 530)
    root.configure(bg=BG)
    executable = tk.StringVar(value=load_installation())
    status = tk.StringVar(value="Kies je bestaande installatie om verder te spelen.")
    process = None
    builder_window = None
    build_active = lambda: False

    def build():
        nonlocal builder_window, build_active
        if builder_window is not None and builder_window.winfo_exists():
            builder_window.lift()
            return
        builder_window, build_active = open_builder(root, executable.set)

    def close():
        if build_active():
            messagebox.showinfo("Build actief", "Laat de gamebuild afronden voordat je de launcher sluit.")
            return
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)

    def label(parent, text, color=TEXT, size=12, **kwargs):
        return tk.Label(parent, text=text, fg=color, bg=parent["bg"],
                        font=("Segoe UI", size), **kwargs)

    def choose():
        value = filedialog.askopenfilename(title="Kies je game", filetypes=[("Game", "*.exe"), ("Alle bestanden", "*")])
        if value:
            try:
                executable.set(str(save_installation(value)))
                status.set("Installatie gekoppeld. Je bestaande instellingen en saves blijven in gebruik.")
            except (OSError, ValueError) as error:
                messagebox.showerror("Installatie kiezen", str(error))

    def play():
        nonlocal process
        if process is not None and process.poll() is None:
            status.set("De game die je via DekuForge startte draait al.")
            return
        try:
            process = launch(executable.get())
            status.set("Game gestart vanuit je bestaande installatie.")
            button.configure(state="disabled")
            root.after(1000, poll)
        except (OSError, ValueError) as error:
            messagebox.showerror("Starten mislukt", str(error))

    def poll():
        if process.poll() is None:
            root.after(1000, poll)
        else:
            button.configure(state="normal")
            status.set(f"Game afgesloten (code {process.returncode}).")

    header = tk.Frame(root, bg=BG, padx=38, pady=24)
    header.pack(fill="x")
    label(header, "DEKU / FORGE", COPPER, 13).pack(anchor="w")
    label(header, "Reforging a legend.", TEXT, 30).pack(anchor="w", pady=(12, 6))
    label(header, "Een nieuwe werkplaats voor jouw avontuur.", GREEN).pack(anchor="w")
    card = tk.Frame(root, bg=PANEL, padx=26, pady=22)
    card.pack(fill="x", padx=38, pady=8)
    label(card, "VERDER SPELEN", GREEN, 11).pack(anchor="w")
    label(card, "Je bestaande installatie", TEXT, 20).pack(anchor="w", pady=(6, 12))
    tk.Entry(card, textvariable=executable, state="readonly", readonlybackground=BG,
             fg=TEXT, relief="flat", font=("Segoe UI", 10)).pack(fill="x", ipady=9)
    actions = tk.Frame(card, bg=PANEL)
    actions.pack(fill="x", pady=(18, 0))
    button = tk.Button(actions, text="Spelen  >", command=play, bg=GREEN, fg=BG,
                       relief="flat", padx=32, pady=10, font=("Segoe UI", 12, "bold"))
    button.pack(side="left")
    tk.Button(actions, text="Installatie kiezen", command=choose, bg=PANEL, fg=TEXT,
              relief="flat", padx=20, pady=10).pack(side="left", padx=10)
    tk.Button(actions, text="NUP / Game bouwen", command=build, bg=COPPER, fg=BG,
              relief="flat", padx=14, pady=10).pack(side="left")
    label(root, "Uitrusting   /   Wereld   /   Geheugen en prestaties", COPPER).pack(anchor="w", padx=38, pady=(18, 4))
    label(root, "Eigen runtime en cheat-integratie worden voorbereid.", TEXT, 10).pack(anchor="w", padx=38)
    tk.Label(root, textvariable=status, fg=GREEN, bg=BG, wraplength=800,
             justify="left", font=("Segoe UI", 10)).pack(anchor="w", padx=38, pady=14)
    label(root, f"DekuForge {__version__}  /  Lokale ontwikkelversie", COPPER, 9).pack(side="bottom", anchor="w", padx=38, pady=12)
    root.mainloop()


if __name__ == "__main__":
    main()
