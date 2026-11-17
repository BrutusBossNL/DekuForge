"""Original single-window mod management; filesystem work stays off Tk's thread."""
from pathlib import Path
from datetime import datetime, timezone
import threading
import sys
import tkinter as tk
from tkinter import filedialog, ttk

from .mods import ModLibrary, rebuild_code
from .theme import BG, PANEL, TEXT, GOLD, MUTED, BackgroundCanvas, ScrolledText


class ModsUI:
    def render_mods(self):
        self.mods_log_widget = None
        self.label(self.content, self.t('mods_help'), 10, MUTED, wraplength=640).pack(anchor='w', pady=(0, 12))
        if not self.executable or not Path(self.executable).is_file():
            self.label(self.content, self.t('mods_no_game'), 11, GOLD, wraplength=620).pack(anchor='w')
            return
        self.label(self.content, self.executable, 9, MUTED, wraplength=640).pack(anchor='w', pady=(0, 8))
        row = BackgroundCanvas(self.content, surface=self.backdrop)
        row.pack(fill='x', pady=(0, 10))
        state = 'disabled' if self.management_busy() else 'normal'
        self.button(row, self.t('mods_add_archive'), self.choose_mod_archive, state=state).pack(side='left', padx=(0, 8))
        self.button(row, self.t('mods_add_folder'), self.choose_mod_folder, state=state).pack(side='left')
        row = BackgroundCanvas(self.content, surface=self.backdrop)
        row.pack(fill='x', pady=(0, 10))
        self.button(row, self.t('mods_open'), self.open_mod_folder, state=state).pack(side='left', padx=(0, 8))
        self.button(row, self.t('mods_refresh'), lambda: self.mods_work('scan'), state=state).pack(side='left')
        listing = tk.Frame(self.content, bg=PANEL)
        listing.pack(fill='x', pady=(0, 12))
        scrollbar = ttk.Scrollbar(listing, orient='vertical')
        scrollbar.pack(side='right', fill='y')
        self.mod_list = tk.Listbox(listing, bg=PANEL, fg=TEXT, selectbackground=GOLD, selectforeground=BG,
                                  relief='flat', borderwidth=0, highlightthickness=0, exportselection=False,
                                  height=6, font=('Segoe UI', 11), yscrollcommand=scrollbar.set)
        self.mod_list.pack(fill='x', expand=True)
        scrollbar.configure(command=self.mod_list.yview)
        for mod in self.mods_entries:
            self.mod_list.insert('end', self.t('mods_row', name=mod.name,
                                 state=self.t('mods_unusable' if mod.problem else 'on' if mod.enabled else 'off'), files=len(mod.romfs)))
        self.mod_list.bind('<<ListboxSelect>>', self.select_mod)
        controls = BackgroundCanvas(self.content, surface=self.backdrop)
        controls.pack(fill='x', pady=(0, 12))
        self.mod_toggle_button = self.button(controls, self.t('mods_enable'), lambda: self.modify_mod('toggle'), state='disabled')
        self.mod_toggle_button.pack(side='left', padx=(0, 8))
        self.mod_up_button = self.button(controls, self.t('mods_up'), lambda: self.modify_mod('up'), state='disabled')
        self.mod_up_button.pack(side='left', padx=(0, 8))
        self.mod_down_button = self.button(controls, self.t('mods_down'), lambda: self.modify_mod('down'), state='disabled')
        self.mod_down_button.pack(side='left')
        self.mod_detail = self.label(self.content, self.t('mods_empty'), 10, MUTED, wraplength=640)
        self.mod_detail.pack(anchor='w', pady=(0, 10))
        for index, mod in enumerate(self.mods_entries):
            if mod.name == self.mod_selected:
                self.mod_list.selection_set(index)
                break
        if self.mods_entries and not self.mod_list.curselection():
            self.mod_list.selection_set(0)
        self.select_mod()
        self.button(self.content, self.t('mods_build_code'), self.request_mod_rebuild, state=state).pack(anchor='w', pady=(0, 10))
        self.label(self.content, self.mods_status or self.t('mods_ready'), 10, GOLD, wraplength=640).pack(anchor='w')
        if self.mods_log or self.mods_busy:
            log = ScrolledText(self.content, height=5, bg=BG, fg=MUTED, relief='flat', font=('Consolas', 9))
            log.insert('1.0', ''.join(self.mods_log[-100:]))
            log.configure(state='disabled')
            log.pack(fill='x', pady=(12, 0))
            self.mods_log_widget = log
        if self.mods_loaded_for != self.executable and not self.mods_busy and '--self-test' not in sys.argv:
            self.root.after_idle(lambda: self.mods_work('scan') if self.page == 'mods' else None)

    def select_mod(self, _event=None):
        selected = self.mod_list.curselection()
        if not selected or selected[0] >= len(self.mods_entries):
            return
        mod = self.mods_entries[selected[0]]
        self.mod_selected = mod.name
        lines = [self.t('mods_selected', name=mod.name)]
        if mod.description:
            lines.append(mod.description)
        lines.append(self.t('mods_counts', files=len(mod.romfs), code=len(mod.code)))
        lines.extend(self.t('mods_file', path=path) for path in list(mod.romfs)[:8])
        lines.extend(self.t('mods_file', path=path) for path in list(mod.code)[:8])
        if mod.problem:
            lines.append(self.t(mod.problem))
        if mod.needs_layout:
            lines.append(self.t('mods_normalize'))
        if mod.code:
            lines.append(self.t('mods_code_help'))
        for path, winner in mod.conflicts[:8]:
            lines.append(self.t('mods_conflict', path=path, winner=winner))
            lines.append(self.t('mods_peers', names=', '.join(mod.conflict_peers.get(path, [])[:8])))
        if len(mod.conflicts) > 8:
            lines.append(self.t('mods_more_conflicts', count=len(mod.conflicts)-8))
        self.mod_detail.configure(text='\n'.join(lines))
        state = 'disabled' if self.management_busy() else 'normal'
        self.mod_toggle_button.configure(text=self.t('mods_disable' if mod.enabled else 'mods_enable'),
                                         state='disabled' if mod.problem and not mod.enabled else state)
        self.mod_up_button.configure(state=state if selected[0] > 0 else 'disabled')
        self.mod_down_button.configure(state=state if selected[0]+1 < len(self.mods_entries) else 'disabled')

    def choose_mod_archive(self):
        if self.management_busy():
            return
        value = filedialog.askopenfilename(parent=self.root, title=self.t('mods_add_archive'),
                                           filetypes=[(self.t('mods_archives'), '*.zip *.7z *.rar')])
        if value:
            self.mods_work('import', value)

    def choose_mod_folder(self):
        if self.management_busy():
            return
        value = filedialog.askdirectory(parent=self.root, title=self.t('mods_add_folder'))
        if value:
            self.mods_work('import', value)

    def open_mod_folder(self):
        if self.management_busy():
            return
        try:
            library = ModLibrary(self.executable)
            library._closed()
            self.open_folder(library.folder)
        except (OSError, ValueError) as error:
            self.show_error(error)

    def modify_mod(self, action):
        if self.mod_selected:
            self.mods_work(action, self.mod_selected)

    def request_mod_rebuild(self):
        if self.management_busy():
            return
        if not self.source or not Path(self.source).is_file():
            self.choose_source()
            if not self.source or not Path(self.source).is_file():
                return
        self.mods_log = []
        self.mods_work('rebuild')

    def mods_work(self, action, value=None, play_after=False):
        if self.management_busy():
            return
        self.mods_busy = True
        self.mods_status = self.t('mods_building' if action == 'rebuild' else 'mods_working')
        executable, source = self.executable, self.source
        self.render()

        def worker():
            try:
                library = ModLibrary(executable)
                prepared_mods = None
                if action == 'import':
                    library.import_mod(value)
                elif action == 'toggle':
                    library.toggle(value)
                elif action in ('up', 'down'):
                    library.move(value, -1 if action == 'up' else 1)
                elif action in ('prepare', 'rebuild'):
                    prepared_mods = library.prepare()
                    if action == 'rebuild':
                        logs = self.library.project/'local/logs'
                        logs.mkdir(parents=True, exist_ok=True)
                        filename = logs/('mods-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.log')
                        with filename.open('x', encoding='utf-8') as output:
                            def notify(kind, data):
                                text = str(data) if kind == 'log' else f'[{kind}] {data}\n'
                                output.write(text)
                                output.flush()
                                self.events.put(('mods_log', text))
                            try:
                                rebuild_code(library, source, notify)
                            except Exception as error:
                                output.write(f'\n[error] {error}\n')
                                raise
                    if library.pending_code(prepared_mods):
                        raise ValueError('mods_rebuild_needed')
                    library.check_code_status(prepared_mods)
                self.events.put(('mods_finished', (executable, library.scan() if prepared_mods is None else prepared_mods, play_after)))
            except Exception as error:
                self.events.put(('mods_error', (str(error), play_after)))
        threading.Thread(target=worker, daemon=False).start()
