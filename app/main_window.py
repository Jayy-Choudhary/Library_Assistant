"""
Library Assistant - main window entry moved from library_assistant.py
"""

import tkinter as tk

from config.theme import (
    COLORS,
    FONT_HEADER,
    FONT_BODY,
    FONT_SMALL,
)

from config.paths import DB_PATH

from database.database import Database
from pages import (
    PageBase,
    DashboardPage,
    StudentsPage,
    SeatsPage,
    FeesPage,
    RoomsPage,
)

# Preserve dialog import structure (prevents previously fixed NameError)
from dialogs import (
    StudentDialog,
    OldStudentDialog,
    PaymentDialog,
    FeeUpdateDialog,
    AddSeatsDialog,
)

from widgets.components import styled_treeview, card, label_entry, action_button


class LibraryAssistant(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Library Assistant")
        self.geometry("1200x720")
        self.minsize(900, 600)
        self.configure(bg=COLORS["sidebar"])

        self.db = Database(DB_PATH)
        self._current_page = None
        self._nav_buttons = {}

        self._build_layout()
        self._show_page("dashboard")

        # Auto-refresh dashboard every 60s
        self._schedule_refresh()

    def _build_layout(self):
        # ── Sidebar ──────────────────────────────
        self.sidebar = tk.Frame(self, bg=COLORS["sidebar"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo area
        logo_frame = tk.Frame(self.sidebar, bg=COLORS["sidebar"], pady=24)
        logo_frame.pack(fill="x")
        tk.Label(
            logo_frame,
            text="📚",
            font=("Helvetica", 28),
            bg=COLORS["sidebar"],
            fg="#FFFFFF",
        ).pack()
        tk.Label(
            logo_frame,
            text="Library\nAssistant",
            font=("Georgia", 15, "bold"),
            bg=COLORS["sidebar"],
            fg="#FFFFFF",
            justify="center",
        ).pack()
        tk.Frame(self.sidebar, bg=COLORS["sidebar_active_bg"], height=1).pack(
            fill="x", pady=8
        )

        # Nav items
        nav_items = [
            ("dashboard", "🏠  Dashboard"),
            ("students", "🎓  Students"),
            ("seats", "💺  Seats"),
            ("fees", "💰  Fees"),
            ("rooms", "🏢  Rooms"),
        ]

        for key, label in nav_items:
            btn = tk.Button(
                self.sidebar,
                text=label,
                font=FONT_BODY,
                fg=COLORS["sidebar_text"],
                bg=COLORS["sidebar"],
                relief="flat",
                bd=0,
                anchor="w",
                padx=28,
                pady=12,
                activebackground=COLORS["sidebar_active_bg"],
                activeforeground="#FFFFFF",
                cursor="hand2",
                command=lambda k=key: self._show_page(k),
            )
            btn.pack(fill="x")
            self._nav_buttons[key] = btn

        # Footer
        tk.Frame(self.sidebar, bg=COLORS["sidebar_active_bg"], height=1).pack(
            fill="x", side="bottom", pady=8
        )
        tk.Label(
            self.sidebar,
            text="v1.0  •  SQLite",
            font=FONT_SMALL,
            bg=COLORS["sidebar"],
            fg=COLORS["sidebar_text"],
        ).pack(side="bottom", pady=6)

        # ── Main content area ─────────────────────
        self.content = tk.Frame(self, bg=COLORS["bg"])
        self.content.pack(side="left", fill="both", expand=True)

        self._pages = {}

    def _show_page(self, key):
        # Update sidebar button styles
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(
                    bg=COLORS["sidebar_active_bg"], fg=COLORS["sidebar_active_text"]
                )
            else:
                btn.configure(bg=COLORS["sidebar"], fg=COLORS["sidebar_text"])

        # Hide current, show new
        if self._current_page and self._current_page in self._pages:
            self._pages[self._current_page].pack_forget()

        # Lazy initialization
        if key not in self._pages:
            if key == "dashboard":
                self._pages["dashboard"] = DashboardPage(self.content, self.db)
            elif key == "students":
                self._pages["students"] = StudentsPage(self.content, self.db)
            elif key == "seats":
                self._pages["seats"] = SeatsPage(self.content, self.db)
            elif key == "fees":
                self._pages["fees"] = FeesPage(self.content, self.db)
            elif key == "rooms":
                self._pages["rooms"] = RoomsPage(self.content, self.db)

        self._pages[key].pack(fill="both", expand=True)
        self._pages[key].refresh()
        self._current_page = key

    def _schedule_refresh(self):
        if self._current_page == "dashboard" and "dashboard" in self._pages:
            self._pages["dashboard"].refresh()
        self.after(60_000, self._schedule_refresh)
