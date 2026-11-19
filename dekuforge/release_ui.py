"""Version list, release-note reader and version-dependent update actions."""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import uuid
import re
import webbrowser

from . import COMPONENTS, __version__
from .releases import REPOSITORY
from .theme import GOLD, PANEL, TEXT, ScrolledText
from .update_service import newer_version, version_key


def displayed_releases(releases, installed=__version__):
    rows = [dict(item) for item in releases]
    if not any(item['version'].removeprefix('v') == installed for item in rows):
        rows.append({'version': 'v'+installed, 'preview': '-' in installed, 'notes': '', 'installable': False})
    return sorted(rows, key=lambda item: version_key(item['version']) or (0,0,0,False,()), reverse=True)


def release_action(version, installed=__version__):
    if version.removeprefix('v') == installed:
        return 'rebuild'
    return 'update' if newer_version(version, installed) else 'downgrade'


class ReleaseListUI:
    def render_release_list(self, parent):
        self.release_rows = displayed_releases(self.releases)
        if self.selected_release not in [r['version'] for r in self.release_rows]:
            self.selected_release = self.release_rows[0]['version']
        self.label(parent, self.t('release_choice'), 11).pack(anchor='w', pady=(18,8))
        panel = tk.Frame(parent, bg=PANEL)
        panel.pack(fill='both', expand=True)
        panel.grid_columnconfigure(0, weight=1, minsize=220)
        panel.grid_columnconfigure(1, weight=2, minsize=270)
        panel.grid_rowconfigure(0, weight=1)
        left = tk.Frame(panel, bg=PANEL)
        left.grid(row=0, column=0, sticky='nsew', padx=(0,14))
        self.release_list = ttk.Treeview(left, columns=('version','channel','status'), show='headings',
                                        selectmode='browse', height=8, style='Forge.Treeview')
        for column, label, width in (('version','release_version',140), ('channel','release_channel_column',75),
                                      ('status','release_status_column',90)):
            self.release_list.heading(column, text=self.t(label))
            self.release_list.column(column, width=width, minwidth=55, stretch=True)
        scroll = ttk.Scrollbar(left, command=self.release_list.yview, style='Forge.Vertical.TScrollbar')
        scroll.pack(side='right', fill='y')
        self.release_list.configure(yscrollcommand=scroll.set)
        self.release_list.pack(fill='both', expand=True)
        self.release_list.tag_configure('preview', foreground=GOLD)
        self.release_list.tag_configure('stable', foreground='#98c9e8')
        self.release_list.tag_configure('current', font=('Segoe UI',10,'bold'))
        for index, row in enumerate(self.release_rows):
            current = release_action(row['version']) == 'rebuild'
            channel = 'preview' if row.get('preview') else 'stable'
            status = 'release_current' if current else 'release_external' if not row.get('installable') else None
            self.release_list.insert('', 'end', iid=str(index), values=(row['version'], self.t(channel),
                self.t(status) if status else ''),
                tags=(channel, 'current' if current else channel))
        right = tk.Frame(panel, bg=PANEL)
        right.grid(row=0, column=1, sticky='nsew')
        self.label(right, self.t('release_notes'), 12, GOLD).pack(anchor='w', pady=(0,8))
        self.release_notes = ScrolledText(right, height=14, width=28, wrap='word', font=('Segoe UI',10),
            bg=PANEL, fg=TEXT, insertbackground=GOLD, relief='flat', padx=12, pady=12)
        self.release_notes.pack(fill='both', expand=True)
        self.release_notes.tag_configure('heading', foreground=GOLD, font=('Segoe UI',11,'bold'), spacing1=8, spacing3=6)
        self.release_notes.tag_configure('strong', font=('Segoe UI',10,'bold'))
        self.release_notes.tag_configure('code', font=('Consolas',9), foreground=GOLD)
        self.release_button = self.button(parent, '', self.perform_release_action, primary=True, pady=7)
        self.release_button.pack(anchor='w', pady=(14,0))
        self.release_list.bind('<<TreeviewSelect>>', self.select_release_row)
        index = next(i for i,row in enumerate(self.release_rows) if row['version'] == self.selected_release)
        self.release_list.selection_set(str(index))
        self.release_list.see(str(index))
        self.select_release_row()

    def select_release_row(self, event=None):
        selection = self.release_list.selection()
        if not selection:
            return
        row = self.release_rows[int(selection[0])]
        self.selected_release = row['version']
        action = self.release_row_action(row)
        self.release_notes.configure(state='normal')
        self.release_notes.delete('1.0','end')
        if action == 'github':
            self.release_notes.insert('end', self.t('release_external_help') + '\n\n')
        for line in (row.get('notes') or self.t('release_notes_empty')).splitlines():
            heading = line.lstrip().startswith('#')
            if heading:
                self.release_notes.insert('end', line.lstrip('# ').replace('**','')+'\n', 'heading')
            else:
                for part in re.split(r'(\*\*.*?\*\*|`[^`]+`)', line):
                    if part.startswith('**') and part.endswith('**'):
                        self.release_notes.insert('end', part[2:-2], 'strong')
                    elif part.startswith('`') and part.endswith('`'):
                        self.release_notes.insert('end', part[1:-1], 'code')
                    else:
                        self.release_notes.insert('end', part)
                self.release_notes.insert('end','\n')
        self.release_notes.configure(state='disabled')
        self.release_notes.yview_moveto(0)
        self.release_button.configure(text=self.t('release_action_'+action),
            state='normal' if not self.management_busy() and version_key(row['version']) else 'disabled')

    @staticmethod
    def release_row_action(row):
        action = release_action(row['version'])
        return 'github' if action != 'rebuild' and not row.get('installable') else action

    def perform_release_action(self):
        row = next((row for row in self.release_rows if row['version'] == self.selected_release), None)
        if not row or not version_key(row['version']) or self.management_busy():
            return
        action = self.release_row_action(row)
        if action == 'github':
            if not webbrowser.open(f"https://github.com/{REPOSITORY}/releases/tag/{row['version']}"):
                self.show_error(self.t('release_browser_failed'))
        elif action == 'rebuild':
            self.rebuild_current_release()
        else:
            self.install_selected_release()

    def rebuild_current_release(self):
        if self.management_busy():
            return
        if not self.source or not Path(self.source).is_file():
            self.choose_source()
            if not self.source or not Path(self.source).is_file():
                return
        from .update_package import atomic_json
        atomic_json(self.library.project/'local/pending-game-update.json', {'components': COMPONENTS, 'requires_rebuild': True,
            'status': 'pending', 'release': 'v'+__version__, 'build_fingerprint': uuid.uuid4().hex})
        self.resume_game_update(manual=True)
