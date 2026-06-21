import tkinter as tk
from tkinter import messagebox

from config.theme import COLORS, FONT_SMALL
from dialogs import AddSeatsDialog

from widgets.components import styled_treeview, action_button

from .page_base import PageBase


class SeatsPage(PageBase):
    def _build(self):
        self._section_header("💺  Seat Management")
        self._divider()

        tb = tk.Frame(self, bg=COLORS["bg"])
        tb.pack(fill="x", padx=28, pady=8)

        action_button(tb, "+ Add Seats", self._add_seats).pack(side="left", padx=4)

        # Seat filters (new): show all + room selectors.
        self.filter_var = tk.StringVar(value="All")
        for val in ("All", "A", "B", "C"):
            tk.Radiobutton(
                tb,
                text=f"Room {val}" if val != "All" else "All",
                variable=self.filter_var,
                value=val,
                font=FONT_SMALL,
                bg=COLORS["bg"],
                fg=COLORS["text_primary"],
                activebackground=COLORS["bg"],
                command=self.refresh,
            ).pack(side="left", padx=6)

        tframe, self.tree = styled_treeview(
            self,
            ["Seat Number", "Room", "Status"],
            {"Seat Number": 160, "Room": 80, "Status": 180},
            height=22,
        )

        tframe.pack(fill="both", expand=True, padx=28, pady=(4, 20))
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = self.db.get_all_seats()
        f_raw = (self.filter_var.get() or "All").strip()
        f = f_raw.upper()
        # Compute seat status from active students (not only seats.status)
        active_rows = self.db.conn.execute(
            "SELECT seat_number, shift_type FROM students WHERE status='Active'"
        ).fetchall()
        active_by_seat = {}
        for ar in active_rows:
            seat_number = ar["seat_number"]
            shift_type = ar["shift_type"] if ar["shift_type"] else "FULL_DAY"
            active_by_seat.setdefault(seat_number, []).append(shift_type)

        for r in rows:
            seat_room = (
                (r["room"] or "A").strip().upper() if "room" in r.keys() else "A"
            )
            if f != "ALL" and seat_room != f:
                continue

            seat_number = r["seat_number"]
            shifts = active_by_seat.get(seat_number, [])

            # Determine display label + tag:
            # - Available: no active students
            # - Occupied: FULL_DAY exists
            # - Half Occ (day): only HALF_DAY_DAY exists
            # - Half Occ (night): only HALF_DAY_NIGHT exists
            # - Doubly occupied: both half types exist
            if not shifts:
                display_status = "Available"
                tag = "avail"
            elif "FULL_DAY" in shifts:
                display_status = "Occupied"
                tag = "occ"
            else:
                has_day = "HALF_DAY_DAY" in shifts
                has_night = "HALF_DAY_NIGHT" in shifts
                if has_day and has_night:
                    display_status = "Doubly occupied"
                    tag = "doubly"
                elif has_day:
                    display_status = "Half Occ (day)"
                    tag = "half_day"
                elif has_night:
                    display_status = "Half Occ (Night)"
                    tag = "half_night"
                else:
                    display_status = "Occupied"
                    tag = "occ"

            self.tree.insert(
                "",
                "end",
                values=(seat_number, seat_room, display_status),
                tags=(tag,),
            )

        self.tree.tag_configure("occ", foreground=COLORS["danger"])
        self.tree.tag_configure("avail", foreground=COLORS["success"])
        self.tree.tag_configure("half_day", foreground="#9CA3AF")  # light grey
        self.tree.tag_configure("half_night", foreground="#9CA3AF")
        self.tree.tag_configure("doubly", foreground="#2563EB")  # blue

    def _add_seats(self):
        dlg = AddSeatsDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            # Backward-compatible: if dialog doesn't provide room explicitly,
            # infer from prefix purely for seat.room persistence during creation.
            room = (d.get("room") or "").strip().upper()
            prefix_room = (d.get("prefix") or "").strip().upper()
            if room not in ("A", "B", "C"):
                room = prefix_room if prefix_room in ("A", "B", "C") else "A"

            added, skipped = self.db.add_seats_bulk(
                d["prefix"], d["start"], d["end"], room=room
            )
            self.refresh()
            messagebox.showinfo(
                "Done", f"Added: {added}  |  Skipped (duplicates): {skipped}"
            )
