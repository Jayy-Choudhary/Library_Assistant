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

        total, occ, avail = self.db.seat_counts()
        active, _old = self.db.count_students()

        self.db.generate_fee_notices()
        due_rows = self.db.get_due_students()
        pending_notices = self.db.get_pending_notice_count()
        reminder_due = len(self.db.get_notice_center_rows("Reminder Due"))
        due_notices = len(self.db.get_notice_center_rows("Due"))
        overdue_notices = len(self.db.get_notice_center_rows("Overdue"))

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

