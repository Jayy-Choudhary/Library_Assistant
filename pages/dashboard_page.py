import tkinter as tk

from config.theme import COLORS, FONT_HEADER
from widgets.components import styled_treeview, card

from .page_base import PageBase


class DashboardPage(PageBase):
    def _build(self):
        self._section_header("📊  Dashboard")
        self._divider()

        # Stat cards row
        self.cards_frame = tk.Frame(self, bg=COLORS["bg"])
        self.cards_frame.pack(fill="x", padx=20, pady=10)
        for i in range(4):
            self.cards_frame.columnconfigure(i, weight=1)

        # Due students table
        tk.Label(
            self,
            text="Fee Due Students",
            font=FONT_HEADER,
            bg=COLORS["bg"],
            fg=COLORS["danger"],
        ).pack(anchor="w", padx=28, pady=(14, 4))

        tframe, self.due_tree = styled_treeview(
            self,
            ["Seat No.", "Student Name", "Due Amount (₹)"],
            {"Seat No.": 110, "Student Name": 240, "Due Amount (₹)": 160},
            height=10,
        )
        tframe.pack(fill="both", expand=True, padx=28, pady=(0, 20))

        self.refresh()

    def refresh(self):
        # Clear old cards
        for w in self.cards_frame.winfo_children():
            w.destroy()

        metrics = self.db.get_dashboard_metrics()
        total = metrics["total_seats"]
        occ = metrics["occupied_seats"]
        avail = metrics["available_seats"]
        active = metrics["active_students"]
        due_rows = metrics["due_students"]
        pending_notices = metrics["pending_notices"]
        reminder_due = metrics["reminder_due"]
        due_notices = metrics["due_notices"]
        overdue_notices = metrics["overdue_notices"]

        card_data = [
            ("Total Seats", total, COLORS["accent"]),
            ("Occupied", occ, COLORS["accent2"]),
            ("Available", avail, COLORS["success"]),
            ("Active Students", active, "#0EA5E9"),
            ("Pending Notices", pending_notices, COLORS["warning"]),
            ("Reminder Due", reminder_due, "#CA8A04"),
            ("Due", due_notices, "#EA580C"),
            ("Overdue", overdue_notices, COLORS["danger"]),
        ]
        for idx, (title, val, color) in enumerate(card_data):
            card(self.cards_frame, title, val, color, col=idx % 4, row=idx // 4)

        # Due tree
        for item in self.due_tree.get_children():
            self.due_tree.delete(item)
        for r in due_rows:
            self.due_tree.insert(
                "",
                "end",
                values=(r["seat_number"], r["full_name"], f"₹{r['due_amount']:.0f}"),
            )
