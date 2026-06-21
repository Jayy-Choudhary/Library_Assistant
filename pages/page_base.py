import tkinter as tk

from config.theme import COLORS, FONT_TITLE


class PageBase(tk.Frame):
    def __init__(self, parent, db):
        super().__init__(parent, bg=COLORS["bg"])
        self.db = db
        self._build()

    def _build(self):
        pass

    def refresh(self):
        pass

    def _section_header(self, text, parent=None):
        p = parent or self
        f = tk.Frame(p, bg=COLORS["bg"])
        tk.Label(
            f,
            text=text,
            font=FONT_TITLE,
            bg=COLORS["bg"],
            fg=COLORS["text_primary"],
        ).pack(side="left")
        f.pack(fill="x", padx=28, pady=(22, 6))
        return f

    def _divider(self, parent=None):
        p = parent or self
        tk.Frame(p, bg=COLORS["border"], height=1).pack(
            fill="x", padx=28, pady=4
        )

