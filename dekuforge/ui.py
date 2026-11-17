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

from . import __version__
from . import reports
import webbrowser
from .core import ROOT, launch, load_settings, save_installation, update_settings
from .engine import build_independent
from .i18n import LANGUAGES, MESSAGES, translate
from .native import prepare_archive
from .preferences import DEFAULTS, resolve_language
from .releases import list_releases
from .update_service import prepare_release, start_worker, newer_version
from .game_updates import run_rebuild, game_running
from .build_library import BuildLibrary
from .home_cards import ActionCard, animate_intro
from .saves import export_save, import_save, save_files
from .theme import BG, BORDER, GOLD, LEAF, MUTED, PANEL, TEXT, ArtworkLabel, BackgroundCanvas, apply_identity, apply_window, logo_image
from .workflow import BuildRequest, Progress, duration, validate_destination, validate_source
from .theme import button_feedback, NavigationCanvas, NavigationLogo, PagePanel, ScrolledText


class Launcher:
    def __init__(self, root):
        self.root = root
        root.title("DekuForge")
        root.geometry("1120x760")
        root.minsize(960, 700)
        apply_window(root)
        root.protocol("WM_DELETE_WINDOW", self.close)
        settings = DEFAULTS | load_settings()
        self.preferences = settings
        self.language_choice = settings["language"]
        self.language = resolve_language(self.language_choice)
        self.release_status = ""
        self.releases = []
        self.checked_channel = None
        self.selected_release = ""
        self.library = BuildLibrary(ROOT)
        self.build_busy = False
        self.library_status = ""
        self.library_view = False
        self.intro_cover = None
        self.intro_job = None
        self.card_job = None
        self.release_busy = False
        self.report_busy = False
        self.report_load_failed = False
        self.report_context = None
        self.report_authenticated = False
        self.report_status = ""
        self.report_incident = None
        self.report_draft = {"title":"", "details":"", "expected":"", "include_logs":True}
        self.report_submitted_url = ""
        self.report_preview = None
        self.update_busy = False
        self.update_job = None
        self.save_busy = False
        self.save_status = ""
        self.save_folder = settings.get("save_folder", "")
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
        self.root.grid_columnconfigure(0, minsize=240)
        self.sidebar = NavigationCanvas(root, width=240)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.pack_propagate(False)
        self.backdrop = BackgroundCanvas(root)
        self.backdrop.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.backdrop.grid_propagate(False)
        self.backdrop.grid_rowconfigure(0, weight=1)
        self.backdrop.grid_columnconfigure(0, weight=1)
        self.page_host = tk.Frame(self.backdrop, bg=BG)
        self.page_host.grid(row=0, column=0, sticky="nsew", padx=(264, 24), pady=24)
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)
        self.content = None
        self.page_panel = None
        tk.Misc.lift(self.sidebar)
        style = ttk.Style(root)
        style.configure("Forge.Horizontal.TProgressbar", troughcolor=PANEL, background=GOLD,
                        bordercolor=BORDER, lightcolor=GOLD, darkcolor=GOLD)
        self.render_navigation()
        if "--self-test" not in sys.argv:
            try:
                self.library.discover(self.executable, self.source)
            except (OSError, ValueError) as error:
                self.library_status = str(error)
        self.render()
        self.tick_job = root.after(100, self.tick)
        root.bind("<Destroy>", self.on_destroy, add="+")
        if settings["check_updates"] and "--self-test" not in sys.argv:
            root.after(2500, self.check_updates)
        if "--self-test" not in sys.argv:
            root.after(3000, self.resume_game_update)
            root.after(1000, self.check_previous_incident)

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
        button = tk.Button(parent, text=text, command=command, bg=GOLD if primary else BORDER,
                         fg=BG if primary else TEXT, activebackground=LEAF, activeforeground=BG,
                         font=("Segoe UI", 11, "bold" if primary else "normal"),
                         disabledforeground=BG if primary else MUTED,
                         relief="flat", borderwidth=0, padx=18, pady=options.pop("pady", 11), cursor="hand2", **options)
        return button_feedback(button, primary)

    def card(self, parent, padding=22):
        # Sections share the page surface; spacing replaces stacked inner boxes.
        frame = BackgroundCanvas(parent, surface=self.backdrop, opacity=0.15)
        frame.pack(fill="x", pady=(8, 24))
        return frame

    def render_navigation(self):
        self.cancel_intro()
        for child in self.sidebar.winfo_children():
            child.destroy()
        image = logo_image(self.root, width=210, height=120)
        if image is not None:
            mark = NavigationLogo(self.sidebar, image)
            mark.image = image
            self.logo_label = mark
            mark.pack(padx=14, pady=(32, 6))
        else:
            self.label(self.sidebar, "DekuForge", 22, GOLD).pack(padx=20, pady=30)
        self.label(self.sidebar, self.t("tagline"), 10, MUTED).pack(padx=22, pady=(0, 32))
        for name in ("home", "updates", "saves", "build", "settings", "report"):
            selected = self.page == name
            self.button(self.sidebar, self.t(name), lambda value=name: self.navigate(value),
                        primary=selected, anchor="w").pack(fill="x", padx=16, pady=5)
        self.label(self.sidebar, f"{self.t('development')}\n{__version__}", 9, MUTED).pack(side="bottom", padx=22, pady=24)

    def navigate(self, page):
        self.cancel_intro()
        self.page = page
        self.render_navigation()
        self.render()

    def render(self):
        if self.card_job is not None:
            self.root.after_cancel(self.card_job)
            self.card_job = None
        if self.progressbar is not None:
            self.progressbar.stop()
        self.log_widget = self.progressbar = self.time_label = self.phase_label = None
        for child in self.page_host.winfo_children():
            child.destroy()
        self.page_host.grid_configure(padx=(252, 12) if self.page == "home" else (264, 24),
                                      pady=12 if self.page == "home" else 24)
        self.page_panel = None
        if self.page == "home":
            self.content = BackgroundCanvas(self.page_host, surface=self.backdrop)
            self.content.grid(row=0, column=0, sticky="nsew")
        else:
            self.page_panel = PagePanel(self.page_host, self.backdrop)
            self.page_panel.grid(row=0, column=0, sticky="nsew")
            self.content = self.page_panel.body
        if self.page == "home":
            self.render_home()
        elif self.page == "settings":
            self.render_settings()
        elif self.page == "updates":
            self.render_updates()
        elif self.page == "saves":
            self.render_saves()
        elif self.page == "report":
            self.render_report()
        else:
            if self.library_view:
                self.render_library()
            else:
                self.render_build()
        self.backdrop._schedule_resize(None)

    def build_entries(self):
        try:
            return self.library.prune_missing()
        except (ValueError, OSError) as error:
            self.library_status = str(error)
            return []

    def build_version(self, entry=None):
        if entry is None:
            entry = next((e for e in self.build_entries() if e["executable"] == self.executable), {})
        return entry.get("version") or self.t("custom_game")

    def render_home(self):
        selected = bool(self.executable and Path(self.executable).is_file())
        running = self.process is not None and self.process.poll() is None
        self.home_deck = BackgroundCanvas(self.content, surface=self.backdrop)
        self.home_deck.pack(fill="both", expand=True)
        release = (self.releases[0]["version"] if self.releases and
                   self.checked_channel == self.preferences["update_channel"] else
                   self.t("no_release" if self.checked_channel == self.preferences["update_channel"] else "release_unchecked"))
        version = self.build_version()
        details = ((version if version == self.t("custom_game") else self.t("game_version", version=version)) if selected else self.t("no_install"),
                   self.t("release_found", version=release),
                   self.source or self.t("no_dump"))
        actions = (("play", self.t("playing") if running else self.t("play"), self.play,
                    selected and not running and not self.update_busy and not self.build_busy and not self.save_busy),
                   ("update", self.t("action_update"), lambda: self.navigate("updates"), True),
                   ("build", self.t("action_build"), self.open_wizard, True))
        self.home_cards = []
        for i, ((image, title, command, enabled), detail) in enumerate(zip(actions, details)):
            card = ActionCard(self.home_deck, ROOT / "assets" / "branding" / f"home-{image}.png",
                              title, detail, command, enabled,
                              badge=self.t(self.preferences["update_channel"]) if image == "update" else "",
                              badge_color="#87bcec" if self.preferences["update_channel"] == "stable" else GOLD)
            card.place(relx=i / 3, x=4, y=0, relwidth=1/3, width=-8, relheight=1)
            self.home_cards.append(card)

    def open_wizard(self, fresh=False):
        if fresh and not self.progress.active:
            self.error, self.result, self.log_lines = "", None, []
            self.progress = Progress()
            self.step = 0
            self.destination = str(ROOT / "build" / "installations" / datetime.now().strftime("%Y%m%d-%H%M%S"))
        self.library_view = False
        self.navigate("build")

    def animate_cards(self):
        if self.page != "home":
            return
        cards = list(self.home_cards)
        def frame(step=0):
            self.card_job = None
            for i, card in enumerate(cards):
                if not card.winfo_exists():
                    return
                t = max(0, min(1, (step - i * 5) / 12))
                card.place_configure(y=int((1-t)**3 * max(100, self.home_deck.winfo_height())))
            if step < 22:
                self.card_job = self.root.after(25, lambda: frame(step + 1))
        frame()

    def cancel_intro(self):
        if self.intro_job is not None:
            self.root.after_cancel(self.intro_job)
            self.intro_job = None
        if self.intro_cover is not None:
            self.intro_cover.destroy()
            self.intro_cover = None
            self.sidebar.place_forget()
            self.sidebar.grid()
            tk.Misc.lift(self.sidebar)
            mark = getattr(self, "logo_label", None)
            if mark is not None and mark.winfo_exists():
                mark.configure(image=mark.image)

    def on_destroy(self, event):
        if event.widget is self.root:
            # Include ttk's internal timers and redraws queued during teardown.
            for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
                self.root.tk.call("after", "cancel", job)

    def render_settings(self):
        card = self.card(self.content, padding=12)
        self.label(card, self.t("language"), 16).pack(anchor="w", pady=(0, 8))
        choices = {"system": self.t("system"), **LANGUAGES}
        value = tk.StringVar(value=choices.get(self.language_choice, choices["system"]))
        combo = ttk.Combobox(card, values=list(choices.values()), textvariable=value,
                             state="readonly", style="Forge.TCombobox", font=("Segoe UI", 12), width=24)
        combo.pack(anchor="w")

        def change(_):
            self.set_language(next(code for code, title in choices.items() if title == value.get()))
        combo.bind("<<ComboboxSelected>>", change)
        options = self.card(self.content, padding=12)
        for key, enabled, command, available in (
                ("check_updates", self.preferences["check_updates"], self.toggle_updates, True),
                ("auto_update", self.preferences["auto_update"], self.toggle_auto_update, True),
                ("hide", self.hide_playing, self.toggle_hide, True),
                ("keep_cache", True, lambda: None, False)):
            row = BackgroundCanvas(options, surface=self.backdrop, opacity=0.15)
            row.pack(fill="x", pady=3)
            self.label(row, self.t(key), 11).pack(side="left")
            self.button(row, self.t("on" if enabled else "off"), command, primary=enabled,
                        state="normal" if available else "disabled", pady=4).pack(side="right")
        row = BackgroundCanvas(options, surface=self.backdrop, opacity=0.15)
        row.pack(fill="x", pady=4)
        self.label(row, self.t("update_channel")).pack(side="left")
        self.button(row, self.t(self.preferences["update_channel"]), self.toggle_channel, pady=4).pack(side="right")
        self.label(options, self.t("update_pending"), 9, MUTED, wraplength=620).pack(anchor="w", pady=(8, 0))
        self.label(options, self.t("cache_help"), 9, MUTED, wraplength=620).pack(anchor="w")
        self.button(self.content, self.t("open_log"), lambda: self.open_folder(ROOT / "local" / "logs")).pack(anchor="w", pady=8)
        installed=(ROOT/"local/installation.json").is_file() and (ROOT/"DekuForge-Uninstall.exe").is_file()
        self.button(self.content,self.t("uninstall"),self.uninstall,pady=6,state="normal" if installed and not self.management_busy() else "disabled").pack(anchor="w",pady=4)

    def uninstall(self):
        if self.management_busy() or self.report_busy:return
        import subprocess
        subprocess.Popen([str(ROOT/"DekuForge-Uninstall.exe")],cwd=ROOT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        self.close()

    def set_language(self, code):
        if code not in LANGUAGES and code != "system":
            return
        self.persist({"language": code})
        self.language_choice = code
        self.language = resolve_language(code)
        self.render_navigation()
        self.render()

    def toggle_auto_update(self):
        self.preferences["auto_update"] = not self.preferences["auto_update"]
        self.persist({"auto_update": self.preferences["auto_update"]})
        self.render()

    def toggle_hide(self):
        self.hide_playing = not self.hide_playing
        self.persist({"hide_playing": self.hide_playing})
        self.render()

    def toggle_updates(self):
        self.preferences["check_updates"] = not self.preferences["check_updates"]
        self.persist({"check_updates": self.preferences["check_updates"]})
        self.render()

    def toggle_channel(self):
        self.preferences["update_channel"] = "preview" if self.preferences["update_channel"] == "stable" else "stable"
        self.persist({"update_channel": self.preferences["update_channel"]})
        self.release_status = ""
        self.releases = []
        self.selected_release = ""
        self.render()
        self.check_updates()

    def render_updates(self):
        card = self.card(self.content)
        self.label(card, self.t("installed_version", version=__version__), 16).pack(anchor="w")
        self.label(card, self.t("update_channel") + ": " + self.t(self.preferences["update_channel"])).pack(anchor="w", pady=12)
        self.label(card, self.release_status or self.t("not_started"), wraplength=620).pack(anchor="w", pady=12)
        self.button(card, self.t("working" if self.release_busy else "check_now"), self.check_updates,
                    primary=True, state="disabled" if self.release_busy else "normal").pack(anchor="w")
        self.label(card, self.t("release_choice"), 11).pack(anchor="w", pady=(18, 8))
        versions = [r["version"] for r in self.releases]
        value = tk.StringVar(value=self.selected_release or (versions[0] if versions else ""))
        choice = ttk.Combobox(card, textvariable=value, values=versions, state="readonly" if versions else "disabled",
                              style="Forge.TCombobox")
        choice.pack(fill="x")
        choice.bind("<<ComboboxSelected>>", lambda e: setattr(self, "selected_release", value.get()))
        self.button(card, self.t("install_release"), self.install_selected_release,
                    state="normal" if any(r.get("installable") for r in self.releases) and not self.management_busy() else "disabled", pady=5).pack(anchor="w", pady=(10, 0))
        self.label(self.content, self.t("update_pending"), color=MUTED, wraplength=620).pack(anchor="w")
        if (ROOT / "local/pending-game-update.json").is_file():
            self.button(self.content, self.t("rebuild_update"), lambda: self.resume_game_update(manual=True), pady=5).pack(anchor="w")
        self.button(self.content, self.t("local_versions"), self.open_library).pack(anchor="w", pady=12)

    def install_selected_release(self, automatic=False):
        if self.management_busy():
            return
        release = next((r for r in self.releases if r["version"] == self.selected_release), self.releases[0] if self.releases else None)
        if not release or not release.get("installable"):
            self.release_status = self.t("release_incompatible")
            self.render()
            return
        if not automatic and not messagebox.askyesno("DekuForge", self.t("update_confirm", version=release["version"]), parent=self.root):
            return
        self.update_busy = True
        self.release_status = self.t("update_downloading")
        self.render()
        def work():
            try:
                job = prepare_release(release, lambda done,total: self.events.put(("update_progress", (done,total))))
                self.events.put(("update_ready", job))
            except Exception as error:
                self.events.put(("update_error", str(error)))
        threading.Thread(target=work, daemon=True).start()

    def resume_game_update(self, manual=False):
        pending = ROOT / "local/pending-game-update.json"
        if not pending.is_file() or self.management_busy():
            return
        state = json.loads(pending.read_text(encoding="utf-8"))
        if not state.get("requires_rebuild") or state.get("status") == "complete" or state.get("status") == "failed" and not manual:
            return
        if not Path(self.source).is_file() or game_running():
            self.release_status = self.t("update_rebuild_wait")
            if self.page == "updates": self.render()
            return
        self.build_busy = True
        self.progress = Progress(); self.progress.begin()
        self.log_lines = []; self.error = ""; self.result = None
        folder=ROOT/"local/logs";folder.mkdir(parents=True,exist_ok=True)
        self.log_path=folder/("update-build-"+datetime.now().strftime("%Y%m%d-%H%M%S")+".log")
        self.step = 2; self.page = "build"; self.library_view = False
        self.render_navigation(); self.render()
        def work():
            try:
                with self.log_path.open("w",encoding="utf-8") as log:
                    def notify(kind,value):
                        log.write(f"[{kind}] {value}\n");log.flush()
                        self.events.put((kind,value))
                    result = run_rebuild(notify)
                self.events.put(("update_build_complete", str(result)))
            except Exception as error:
                self.events.put(("failure", str(error)))
            finally:
                self.events.put(("done", None))
        threading.Thread(target=work, daemon=True).start()

    def automatic_update_allowed(self, release):
        result=ROOT/"local/update-result.json"
        try:
            previous=json.loads(result.read_text(encoding="utf-8"))
            return previous.get("success") is not False or previous.get("release")!=release["version"]
        except (OSError,ValueError):
            return True

    def check_updates(self):
        if self.release_busy:
            return
        self.release_busy = True
        channel = self.preferences["update_channel"]
        preview = channel == "preview"
        def work():
            try:
                self.events.put(("release", (channel, list_releases(preview))))
            except Exception as error:
                self.events.put(("release_error", (channel, str(error))))
        threading.Thread(target=work, daemon=True).start()
        if self.page == "updates":
            self.render()

    def check_previous_incident(self):
        incident=reports.previous_incident(ROOT)
        seen=ROOT/"local/report-seen.json"
        try:previous=json.loads(seen.read_text(encoding="utf-8"))
        except (OSError,ValueError):previous=None
        if incident and incident!=previous:
            self.report_incident=incident
            self.report_status=self.t("report_previous")
            self.navigate("report")

    def prepare_report(self):
        if self.report_busy or self.report_load_failed or self.report_context is not None:
            return
        if "--self-test" in sys.argv:
            self.report_context={"metadata":{"launcher":__version__},"logs":[]}
            return
        self.report_busy=True
        def work():
            try:
                context=reports.collect(ROOT,self.executable,self.report_incident)
                from .update_service import github_token
                self.events.put(("report_ready",(context,bool(github_token()))))
            except Exception as error:self.events.put(("report_error",str(error)))
        threading.Thread(target=work,daemon=True).start()

    def render_report(self):
        self.prepare_report()
        self.label(self.content,self.report_status or self.t("report_help"),10,MUTED,wraplength=640).pack(anchor="w",pady=(0,8))
        card=self.card(self.content,padding=12)
        system=(self.report_context or {}).get("metadata",{}).get("system",{})
        if system:
            unknown=self.t("report_unknown")
            gpus=", ".join(gpu["model"]+" / "+gpu.get("driver",unknown) for gpu in system.get("gpus",[])) or unknown
            summary="OS: "+system.get("os",unknown)+"\nCPU: "+system.get("cpu",unknown)+" | RAM: "+str(system.get("ram_gib",unknown))+" GiB\nGPU: "+gpus
            self.label(card,summary,9,MUTED,wraplength=620).pack(anchor="w",pady=(0,8))
        self.label(card,self.t("report_title"),10).pack(anchor="w")
        title=tk.StringVar(value=self.report_draft["title"])
        entry=tk.Entry(card,textvariable=title,bg=PANEL,fg=TEXT,insertbackground=GOLD,relief="flat",font=("Segoe UI",11))
        entry.pack(fill="x",pady=(3,6))
        def title_changed(*_):
            self.report_draft["title"]=title.get();self.report_submitted_url="";self.refresh_report_preview()
        title.trace_add("write",title_changed)
        for key,label,height in (("details","report_details",3),("expected","report_expected",1)):
            self.label(card,self.t(label),10).pack(anchor="w")
            widget=ScrolledText(card,height=height,wrap="word",font=("Segoe UI",10),bg=PANEL,fg=TEXT,
                insertbackground=GOLD,relief="flat",borderwidth=0)
            widget.insert("1.0",self.report_draft[key]);widget.pack(fill="x",pady=(3,6))
            def changed(_event=None,field=key,control=widget):
                try:self.report_draft[field]=control.get("1.0","end-1c")
                except tk.TclError:return
                self.report_submitted_url="";self.refresh_report_preview()
            widget.bind("<KeyRelease>",changed);widget.bind("<FocusOut>",changed)
        include=tk.BooleanVar(value=self.report_draft["include_logs"])
        def toggle():self.report_draft["include_logs"]=include.get();self.report_submitted_url="";self.refresh_report_preview()
        tk.Checkbutton(card,text=self.t("report_logs"),variable=include,command=toggle,bg=PANEL,fg=TEXT,
            activebackground=PANEL,activeforeground=GOLD,selectcolor=BG,relief="flat").pack(anchor="w")
        self.label(card,self.t("report_preview"),10).pack(anchor="w",pady=(6,3))
        self.report_preview=ScrolledText(card,height=7,wrap="word",font=("Consolas",9),bg=BG,fg=TEXT,relief="flat")
        self.report_preview.pack(fill="x")
        self.refresh_report_preview()
        buttons=BackgroundCanvas(self.content,surface=self.backdrop)
        buttons.pack(fill="x")
        ready=self.report_context is not None and not self.report_busy
        self.button(buttons,self.t("report_direct"),self.submit_report,primary=True,pady=6,
            state="normal" if ready and self.report_authenticated and not self.report_submitted_url else "disabled").pack(side="left",padx=(0,6))
        self.button(buttons,self.t("report_browser"),self.open_report_browser,pady=6,state="normal" if ready else "disabled").pack(side="left",padx=(0,6))
        self.button(buttons,self.t("report_export"),self.export_report,pady=6,state="normal" if ready else "disabled").pack(side="left")
        self.label(self.content,self.t("report_auth"),9,MUTED,wraplength=640).pack(anchor="w",pady=(8,0))
        if self.report_load_failed:
            self.button(self.content,self.t("check_now"),self.retry_report,pady=5).pack(anchor="w")
        if self.report_incident:
            from .update_package import atomic_json
            atomic_json(ROOT/"local/report-seen.json",self.report_incident)

    def retry_report(self):
        self.report_load_failed=False;self.report_context=None;self.report_status="";self.render()

    def refresh_report_preview(self):
        if self.report_preview is None or not self.report_preview.winfo_exists():return
        draft=dict(self.report_draft)
        draft["title"]=draft["title"] or self.t("report_title")
        draft["details"]=draft["details"] or self.t("report_details")
        context=self.report_context or {"metadata":{},"logs":[]}
        text=reports.body(draft,context)
        self.report_preview.configure(state="normal");self.report_preview.delete("1.0","end")
        self.report_preview.insert("1.0",text);self.report_preview.configure(state="disabled")

    def open_report_browser(self):
        try:webbrowser.open(reports.browser_url(self.report_draft,self.report_context))
        except (ValueError,OSError) as error:self.show_error(error)

    def export_report(self):
        try:text=reports.body(self.report_draft,self.report_context)
        except ValueError as error:self.show_error(error);return
        filename=filedialog.asksaveasfilename(parent=self.root,initialfile="DekuForge-bug-report.txt",defaultextension=".txt",filetypes=[("Text","*.txt")])
        if filename:Path(filename).write_text(text,encoding="utf-8")

    def submit_report(self):
        if self.report_busy:return
        try:reports.body(self.report_draft,self.report_context)
        except ValueError as error:self.show_error(error);return
        self.report_busy=True
        draft=dict(self.report_draft);context=self.report_context
        self.report_status=self.t("working");self.render()
        def work():
            try:self.events.put(("report_sent",reports.submit(draft,context)))
            except Exception as error:self.events.put(("report_error",str(error)))
        threading.Thread(target=work,daemon=True).start()

    def render_saves(self):
        self.label(self.content, self.t("save_help"), color=MUTED, wraplength=620).pack(anchor="w", pady=(0, 18))
        card = self.card(self.content)
        self.path_row(card, self.t("save_folder"), self.save_folder, self.choose_save_folder)
        for key, action in (("export_save", "export"), ("import_zip", "zip"), ("import_folder", "folder")):
            self.button(card, self.t(key), lambda value=action: self.save_action(value),
                        state="normal" if self.save_folder and not self.save_busy else "disabled").pack(fill="x", pady=5)
        if self.save_folder:
            self.button(card, self.t("open_folder"), lambda: self.open_folder(Path(self.save_folder))).pack(anchor="w", pady=5)
        self.label(self.content, self.save_status, wraplength=620).pack(anchor="w")

    def choose_save_folder(self):
        value = filedialog.askdirectory(parent=self.root, title=self.t("save_folder"))
        if value:
            try:
                save_files(value, require_progress=False)
                self.persist({"save_folder": value})
                self.save_folder = value
                self.render()
            except (ValueError, OSError) as error:
                self.show_error(error)

    def save_action(self, action):
        if self.management_busy():
            return
        if action == "export":
            value = filedialog.asksaveasfilename(parent=self.root, defaultextension=".zip", filetypes=[("ZIP", "*.zip")])
        elif action == "zip":
            value = filedialog.askopenfilename(parent=self.root, filetypes=[("ZIP", "*.zip")])
        else:
            value = filedialog.askdirectory(parent=self.root, title=self.t("import_folder"))
        if not value:
            return
        if action != "export" and not messagebox.askyesno("DekuForge", self.t("save_confirm", folder=self.save_folder), parent=self.root):
            return
        destination = self.save_folder
        self.save_busy = True
        self.save_status = self.t("working")
        self.render()
        def work():
            try:
                if action == "export":
                    export_save(destination, value)
                    result = value
                else:
                    result = str(import_save(value, destination))
                self.events.put(("save_complete", result))
            except Exception as error:
                self.events.put(("save_error", str(error)))
        threading.Thread(target=work, daemon=True).start()

    def render_build(self):
        self.button(self.content, self.t("manage_builds"), self.open_library, pady=5).pack(anchor="e", pady=(0, 8))
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

    def open_library(self):
        self.library_view = True
        self.navigate("build")

    def render_library(self):
        self.label(self.content, self.t("manage_builds"), 19).pack(anchor="w", pady=(0, 12))
        self.library_entries = self.build_entries()
        list_frame = tk.Frame(self.content, bg=PANEL)
        list_frame.pack(fill="x")
        scroll = ttk.Scrollbar(list_frame)
        scroll.pack(side="right", fill="y")
        self.build_list = tk.Listbox(list_frame, bg=PANEL, fg=TEXT, selectbackground=GOLD,
                                    selectforeground=BG, font=("Segoe UI", 11), height=7, exportselection=False)
        self.build_list.pack(fill="x", expand=True)
        scroll.configure(command=self.build_list.yview)
        self.build_list.configure(yscrollcommand=scroll.set)
        for entry in self.library_entries:
            active = entry["executable"] == self.executable
            self.build_list.insert("end", ("● " if active else "  ") + self.build_version(entry) + " — " + str(Path(entry["executable"]).parent))
        self.build_list.bind("<<ListboxSelect>>", self.select_library_entry)
        self.library_detail = self.label(self.content, self.t("build_empty") if not self.library_entries else "", 10, MUTED, wraplength=650)
        self.library_detail.pack(anchor="w", pady=12)
        row = BackgroundCanvas(self.content, surface=self.backdrop)
        row.pack(fill="x")
        self.activate_button = self.button(row, self.t("activate_build"), self.activate_build, primary=True, state="disabled")
        self.activate_button.pack(side="left")
        self.delete_button = self.button(row, self.t("delete_build"), self.delete_build, state="disabled")
        self.delete_button.pack(side="right")
        self.label(self.content, self.library_status, 10, MUTED, wraplength=650).pack(anchor="w", pady=12)
        self.button(self.content, self.t("new_build"), lambda: self.open_wizard(fresh=True)).pack(anchor="w", pady=8)
        self.button(self.content, self.t("choose_install"), self.choose_installation).pack(anchor="w", pady=8)
        if self.library_entries:
            self.build_list.selection_set(0)
            self.select_library_entry()

    def selected_build(self):
        selection = self.build_list.curselection()
        return self.library_entries[selection[0]] if selection else None

    def management_busy(self):
        return self.report_busy or self.update_busy or self.build_busy or self.save_busy or self.progress.active or (self.process is not None and self.process.poll() is None)

    def select_library_entry(self, _event=None):
        entry = self.selected_build()
        if not entry:
            return
        busy = self.management_busy()
        self.library_detail.configure(text=entry["executable"] + "\n" + (entry.get("dump") or self.t("no_dump")))
        self.activate_button.configure(state="normal" if not busy and Path(entry["executable"]).is_file() else "disabled")
        self.delete_button.configure(state="normal" if not busy and entry["owned"] else "disabled")

    def activate_build(self):
        entry = self.selected_build()
        if not entry or self.management_busy():
            return
        try:
            self.executable = str(save_installation(entry["executable"]))
            self.activity = ""
            self.render()
        except (OSError, ValueError) as error:
            self.show_error(error)

    def delete_build(self):
        entry = self.selected_build()
        if not entry or self.management_busy():
            return
        folder = str(Path(entry["executable"]).parent)
        if self.source and Path(self.source).resolve().is_relative_to(Path(folder).resolve()):
            self.show_error(self.t("dump_inside_build"))
            return
        if not messagebox.askyesno(self.t("delete_build"), self.t("delete_confirm", path=folder), parent=self.root, default="no"):
            return
        keep = messagebox.askyesnocancel(self.t("saves"), self.t("keep_saves_question"), parent=self.root, default="yes")
        if keep is None:
            return
        self.build_busy = True
        self.render()
        def worker():
            try:
                backup = self.library.delete(entry["id"], keep)
                self.events.put(("build_deleted", (entry["executable"], str(backup) if backup else "")))
            except Exception as error:
                self.events.put(("build_delete_error", str(error)))
        threading.Thread(target=worker, daemon=False).start()

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
        row = BackgroundCanvas(self.content, surface=self.backdrop)
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
        if self.management_busy():
            return
        value = filedialog.askopenfilename(parent=self.root, title=self.t("select_exe"), filetypes=[(self.t("game_file"), "*.exe"), (self.t("all_files"), "*")])
        if value:
            try:
                self.executable = str(save_installation(value))
                self.library.register(self.executable)
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
        if self.update_busy or self.build_busy or self.save_busy or (self.process is not None and self.process.poll() is None):
            return
        try:
            self.process = launch(self.executable)
            reports.record_run(ROOT,self.process,self.executable)
            self.activity = self.t("playing")
            self.render()
            if self.hide_playing:
                self.root.withdraw()
        except (OSError, ValueError) as error:
            self.show_error(error)

    def start_build(self):
        if self.management_busy():
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
        if self.tick_job is not None:
            self.root.after_cancel(self.tick_job)
        self.tick_job = None
        changed = False
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except Empty:
                break
            if kind == "report_ready":
                self.report_context,self.report_authenticated = value
                self.report_busy = False
                self.report_status = ""
                changed = self.page == "report" or changed
                continue
            if kind == "report_error":
                self.report_busy = False
                self.report_load_failed = self.report_context is None
                self.report_status = self.t("report_send_error",error=value)
                changed = self.page == "report" or changed
                continue
            if kind == "report_sent":
                self.report_busy = False
                self.report_submitted_url = value
                self.report_status = self.t("report_sent",url=value)
                changed = self.page == "report" or changed
                continue
            if kind == "update_progress":
                self.release_status = self.t("update_download_progress", percent=int(value[0]*100/value[1]))
                changed = self.page == "updates" or changed
                continue
            if kind == "update_error":
                self.update_busy = False
                self.release_status = self.t("update_error", error=value)
                changed = True
                continue
            if kind == "update_ready":
                try:
                    start_worker(value)
                    self.cancel_intro()
                    self.root.destroy()
                    return
                except Exception as error:
                    self.update_busy = False
                    self.release_status = str(error)
                    changed = True
                continue
            if kind == "update_build_complete":
                self.result = value; self.executable = value
                self.activity = self.t("update_game_ready")
                changed = True
                continue
            if kind in ("release", "release_error"):
                self.release_busy = False
                channel, result = value
                if channel != self.preferences["update_channel"]:
                    self.check_updates()
                    continue
                self.checked_channel = channel
                if kind == "release":
                    self.releases = result
                    self.selected_release = result[0]["version"] if result else ""
                    if result and result[0].get("installable") and self.preferences["auto_update"] and newer_version(result[0]["version"], __version__) and self.automatic_update_allowed(result[0]) and not self.management_busy():
                        self.install_selected_release(automatic=True)
                    self.release_status = self.t("release_found", version=result[0]["version"]) if result else self.t("release_none")
                else:
                    self.release_status = str(result)
                changed = self.page in ("updates", "home") or changed
                continue
            if kind in ("build_deleted", "build_delete_error"):
                self.build_busy = False
                if kind == "build_deleted":
                    executable, backup = value
                    if executable == self.executable:
                        self.executable = ""
                        self.persist({"executable": ""})
                    self.library_status = self.t("build_deleted") + ("\n" + self.t("saves_retained", path=backup) if backup else "")
                else:
                    self.library_status = str(value)
                changed = True
                continue
            if kind in ("save_complete", "save_error"):
                self.save_busy = False
                self.save_status = self.t("save_done", path=value) if kind == "save_complete" else str(value)
                changed = self.page == "saves" or changed
                continue
            if kind in ("progress", "phase"):
                self.progress.update(value)
            if kind in ("log", "checked", "failure"):
                self.log_lines.append(str(value).rstrip() + "\n")
            if kind == "success":
                self.result = value
                try:
                    self.library.register(value, self.source, owned=True)
                except (OSError, ValueError) as error:
                    self.library_status = str(error)
            elif kind == "failure":
                self.error = self.t(value) if value in MESSAGES["en"] else value
            elif kind == "done":
                self.progress.finish()
                self.build_busy = False
                changed = True
        if len(self.log_lines) > 1600:
            self.log_lines = self.log_lines[-900:]
            self.last_log_length = 0
            if self.log_widget is not None:
                self.log_widget.configure(state="normal")
                self.log_widget.delete("1.0", "end")
                self.log_widget.configure(state="disabled")
        if self.process is not None and self.process.poll() is not None:
            code=self.process.returncode
            self.activity = self.t("game_ended", code=code)
            incident=reports.record_exit(ROOT,code)
            if incident:
                self.report_incident=incident
                self.report_context=None
                self.report_draft["title"]="Game exited unexpectedly (code "+str(code)+")"
                self.report_status=self.t("report_crash",code=code)
                self.page="report"
                self.render_navigation()
            self.process = None
            self.root.deiconify()
            changed = True
        if changed:
            self.render()
        self.refresh_progress()
        self.tick_job = self.root.after(100, self.tick)

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
        if self.report_busy or self.update_busy or self.progress.active or self.save_busy or self.build_busy:
            messagebox.showinfo("DekuForge", self.t("active_build"), parent=self.root)
            return
        self.cancel_intro()
        if self.card_job is not None:
            self.root.after_cancel(self.card_job)
        self.root.destroy()


def main():
    apply_identity()
    root = tk.Tk(className="DekuForge")
    root.withdraw()  # Never map the unfinished layout or empty artwork cards.
    root._launcher = Launcher(root)
    root._callback_errors=0
    def callback_error(kind,value,traceback):
        import traceback as trace
        path=ROOT/"local/launcher-crash.log";path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text("".join(trace.format_exception(kind,value,traceback)),encoding="utf-8")
        root._callback_errors+=1
        if root._callback_errors==1:
            app=root._launcher
            app.report_context=None
            app.report_incident={"kind":"launcher_callback","time":datetime.now(timezone.utc).isoformat()}
            app.report_status=app.t("report_previous")
            root.after(0,lambda:app.navigate("report"))
    root.report_callback_exception=callback_error
    if "--self-test" in sys.argv:
        root.deiconify()
        def self_test():
            application = root._launcher
            checked = []
            checked_reports = []
            try:
                for language in LANGUAGES:
                    application.language = language
                    for page in ("home", "updates", "saves", "build", "settings"):
                        application.navigate(page)
                        root.update_idletasks()
                        checked.append(f"{language}/{page}")
                    for step in (1, 2):
                        application.step = step
                        application.navigate("build")
                        root.update_idletasks()
                        checked.append(f"{language}/build/{step}")
                    application.step = 0
                    application.open_library()
                    root.update_idletasks()
                    checked.append(f"{language}/build/library")
                    application.library_view = False
                    application.navigate("report");root.update_idletasks()
                    checked_reports.append(f"{language}/report")
                report = {"screens": checked, "report_screens":checked_reports, "logo_loaded": root._brand_icon.width() > 0,
                          "native_icon_verified": getattr(root, "_native_icon_verified", os.name != "nt"),
                          "top_level_windows": 1 + sum(isinstance(child, tk.Toplevel) for child in root.winfo_children()),
                          "success": True}
            except Exception as error:
                report = {"screens": checked, "success": False, "error": str(error)}
            folder = ROOT / "local"
            folder.mkdir(exist_ok=True)
            (folder / "launcher-selftest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            root.destroy()
        root.after(100, self_test)
    else:
        animate_intro(root._launcher)
        root.deiconify()
        if "--startup-smoke" in sys.argv:
            root.after(2000,lambda:root._launcher.navigate("report"))
            def finish_smoke():
                app=root._launcher
                report={"success":root._callback_errors==0 and app.report_context is not None,"page":app.page,"callback_errors":root._callback_errors,
                        "report_loaded":app.report_context is not None}
                from .update_package import atomic_json
                atomic_json(ROOT/"local/launcher-startup-smoke.json",report)
                root.destroy()
            root.after(6000,finish_smoke)
    root.mainloop()
