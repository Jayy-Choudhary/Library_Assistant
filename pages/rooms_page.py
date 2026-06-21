import tkinter as tk
from tkinter import messagebox

from config.theme import COLORS, FONT_BODY, FONT_HEADER

from .page_base import PageBase
from dialogs import RoomLayoutDialog


class RoomsPage(PageBase):
    """Room-aware visualization.

    Render model (Stage 2A):
    - Load ALL seats from the seats table (authoritative room assignment).
    - Load active students only to compute occupancy/color and tooltip/details.
    - Render every seat belonging to the selected room (vacant seats included).
    """

    COLOR_GREEN = "#22C55E"  # no active
    COLOR_RED = COLORS["danger"] if "danger" in COLORS else "#EF4444"
    COLOR_GREY = "#6B7280"  # half day only
    COLOR_BLUE = COLORS.get("accent2", "#2563EB")  # half-day day+night

    def __init__(self, parent, db):
        # PageBase calls self._build() inside its __init__, so we must define
        # any state used by _build() before calling super().__init__.
        self._ui_built = False
        self.students_cache = []  # active students
        self.grouped_by_seat = {}  # seat_number -> [students]
        self.seats_cache = []  # all seats (authoritative)
        self.seat_state_cache = {}  # seat_number -> computed state

        super().__init__(parent, db)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(
            int(-1 * (event.delta / 120)),
            "units",
        )

    def _build(self):
        if self._ui_built:
            return
        self._ui_built = True

        self._section_header("🏢  Rooms")
        self._divider()

        # Top control bar
        self.controls = tk.Frame(self, bg=COLORS["bg"])
        self.controls.pack(fill="x", padx=28, pady=10)

        self.room_filter_var = tk.StringVar(value="All")
        for label, prefix in (
            ("Room A", "A"),
            ("Room B", "B"),
            ("Room C", "C"),
            ("All Rooms", "ALL"),
        ):
            rb = tk.Radiobutton(
                self.controls,
                text=label,
                variable=self.room_filter_var,
                value=prefix,
                font=FONT_BODY,
                bg=COLORS["bg"],
                fg=COLORS["text_primary"],
                activebackground=COLORS["bg"],
                command=self.refresh,
            )
            rb.pack(side="left", padx=10)

        # [Layout] button (far right)
        from widgets.components import (
            action_button,
        )  # local import to avoid circular deps

        action_button(
            self.controls,
            "[Layout]",
            self.open_layout_dialog,
            color=(
                COLORS.get("accent2", COLORS.get("accent"))
                if isinstance(COLORS, dict)
                else COLORS["accent"]
            ),
        ).pack(side="right", padx=4)

        # Scrollable container

        self.canvas = tk.Canvas(
            self,
            bg=COLORS["bg"],
            highlightthickness=0,
        )

        self.scrollbar = tk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
        )

        self.tiles_container = tk.Frame(
            self.canvas,
            bg=COLORS["bg"],
        )

        self.tiles_container.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas.create_window(
            (0, 0),
            window=self.tiles_container,
            anchor="nw",
        )

        self.canvas.bind_all(
            "<MouseWheel>",
            self._on_mousewheel,
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(
            side="left",
            fill="both",
            expand=True,
            padx=28,
            pady=(0, 20),
        )

        self.scrollbar.pack(
            side="right",
            fill="y",
        )

        # Tooltip label (names only)
        self.tooltip = tk.Label(
            self,
            text="",
            bg="#111827",
            fg="#FFFFFF",
            font=(
                (FONT_BODY[0] if isinstance(FONT_BODY, tuple) else "Arial", 10)
                if isinstance(FONT_BODY, tuple)
                else ("Arial", 10)
            ),
            padx=10,
            pady=6,
        )
        self.tooltip.place_forget()

        self.render_ui()

    # -------------------------
    # Data / Logic layer
    # -------------------------
    def load_active_students(self):
        # Load ONLY active students for occupancy/color/details.
        self.students_cache = list(self.db.conn.execute("""
                SELECT
                    s.id                AS student_id,
                    s.full_name        AS full_name,
                    s.mobile_number    AS mobile_number,
                    s.seat_number      AS seat_number,
                    s.shift_type       AS shift_type,
                    COALESCE(f.due_amount, 0) AS due_amount
                FROM students s
                LEFT JOIN (
                    SELECT
                        student_id,
                        COALESCE(SUM(due_amount), 0) AS due_amount
                    FROM fees
                    GROUP BY student_id
                ) f ON f.student_id = s.id
                WHERE s.status='Active'

                """).fetchall())

    def group_by_seat(self):
        grouped = {}
        for s in self.students_cache:
            seat = s["seat_number"]
            grouped.setdefault(seat, []).append(s)
        self.grouped_by_seat = grouped
        return grouped

    def load_all_seats(self):
        # Authoritative source of seats + room assignment.
        self.seats_cache = list(self.db.get_all_seats())
        return self.seats_cache

    def _normalize_shift(self, shift_type):
        return shift_type if shift_type else "FULL_DAY"

    def compute_seat_state(self, seat_students):
        # Return computed state dict for rendering.
        if not seat_students:
            return {"color": self.COLOR_GREEN, "tooltip": [], "details": []}

        # Collect shifts (from cached rows)
        shifts = [self._normalize_shift(s["shift_type"]) for s in seat_students]

        # GREEN: no students (handled above)
        # RED: any FULL_DAY student present
        if "FULL_DAY" in shifts:
            return {
                "color": self.COLOR_RED,
                "tooltip": self._names(seat_students),
                "details": seat_students,
            }

        # BLUE: one HALF_DAY_DAY and one HALF_DAY_NIGHT sharing the seat
        if (
            len(seat_students) == 2
            and "HALF_DAY_DAY" in shifts
            and "HALF_DAY_NIGHT" in shifts
        ):
            return {
                "color": self.COLOR_BLUE,
                "tooltip": self._names(seat_students),
                "details": seat_students,
            }

        # GREY: exactly one HALF_DAY student (HALF_DAY_DAY or HALF_DAY_NIGHT)
        # (If unexpected combos occur, treat them as grey deterministically.)
        if len(seat_students) == 1 and shifts[0] in ("HALF_DAY_DAY", "HALF_DAY_NIGHT"):
            return {
                "color": self.COLOR_GREY,
                "tooltip": self._names(seat_students),
                "details": seat_students,
            }

        # Fallback (unexpected combos): grey if any half-day, else green-ish.
        return {
            "color": self.COLOR_GREY,
            "tooltip": self._names(seat_students),
            "details": seat_students,
        }

    def _names(self, seat_students):
        names = []
        for s in seat_students:
            # sqlite Row supports indexing
            try:
                names.append(s["full_name"])
            except Exception:
                names.append(str(getattr(s, "full_name", "")))
        return [n for n in names if n]

    def get_students_for_seat(self, seat_id):
        return self.grouped_by_seat.get(seat_id, [])

    # -------------------------
    # UI layer
    # -------------------------
    def render_ui(self):
        self.clear_frame()
        self.render_all_rooms()

    def clear_frame(self):
        for w in self.tiles_container.winfo_children():
            w.destroy()

    def _seat_sort_key(self, seat_number: str):
        # Robust sort for A01.. style, but ignore unknowns.
        if not seat_number:
            return ("~", 10**9)
        letter = seat_number[0]
        try:
            num = int(seat_number[1:])
        except ValueError:
            num = 10**9
        return (letter, num)

    def open_layout_dialog(self):
        # Determine default room from current filter.
        current = (self.room_filter_var.get() or "All").strip().upper()
        room = current if current in ("A", "B", "C") else "A"

        dlg = RoomLayoutDialog(self, self.db, room)
        self.wait_window(dlg)
        if not getattr(dlg, "result", None):
            return

        d = dlg.result
        self.db.set_room_layout(
            d["room"],
            d["rows"],
            d["columns"],
            d["seat_spacing"],
        )
        self.render_all_rooms()

    def render_room(self, room_prefix):
        # ADD THIS
        self.load_all_seats()
        self.load_active_students()
        self.group_by_seat()

        # room_prefix: 'A'|'B'|'C'|'ALL'
        if room_prefix is None:
            room_prefix = "ALL"
        room_prefix = str(room_prefix).upper()

        # Select seats for this room from the seats table.
        if room_prefix == "ALL":
            # For ALL, use Room A layout for visual placement.
            room_for_layout = "A"
            seats = [r["seat_number"] for r in self.seats_cache]
        else:
            room_for_layout = room_prefix
            seats = [
                r["seat_number"]
                for r in self.seats_cache
                if (r["room"] or "A").strip().upper() == room_prefix
            ]

        seats = sorted(seats, key=self._seat_sort_key)

        if not seats:
            tk.Label(
                self.tiles_container,
                text="No seats in this room",
                font=FONT_BODY,
                bg=COLORS["bg"],
                fg=COLORS["text_secondary"],
            ).pack(pady=30)

            return

        # Stage 2B layout-driven placement.
        layout = self.layout_cache.get(room_for_layout) or (5, 5, 8)
        _, columns, seat_spacing = layout
        columns = max(1, int(columns))
        seat_spacing = max(0, int(seat_spacing))
        # Reset previous column configuration
        for i in range(50):
            self.tiles_container.grid_columnconfigure(i, weight=0)

        print("Selected room:", room_prefix)
        print("Seats:", seats)
        for i, seat in enumerate(seats):

            state = self.seat_state_cache.get(seat)
            if state is None:
                state = self.compute_seat_state(self.get_students_for_seat(seat))
                self.seat_state_cache[seat] = state

            tile = tk.Button(
                self.tiles_container,
                text=seat,
                bg=state["color"],
                fg="#FFFFFF",
                activebackground=state["color"],
                relief="flat",
                font=FONT_BODY,
                padx=12,
                pady=10,
                command=lambda sid=seat: self.on_click(sid),
            )
            visual_row = i // columns
            visual_col = i % columns
            tile.grid(
                row=visual_row,
                column=visual_col,
                padx=seat_spacing,
                pady=seat_spacing,
                sticky="nsew",
            )

            tile.bind("<Enter>", lambda e, sid=seat: self.on_hover(e, sid))
            tile.bind("<Leave>", self._on_leave)

        # Expand columns/rows for nice layout (use layout cache column count)
        for i in range(columns):
            self.tiles_container.grid_columnconfigure(i, weight=1)

    def render_all_rooms(self):
        self.clear_frame()

        # Recompute caches each refresh.
        self.load_all_seats()
        self.load_active_students()
        self.group_by_seat()

        # Layout cache (Stage 2B): load once per refresh.
        self.layout_cache = {
            "A": self.db.get_room_layout("A"),
            "B": self.db.get_room_layout("B"),
            "C": self.db.get_room_layout("C"),
        }

        self.seat_state_cache = {}
        # Precompute only for seats that have active students; vacant seats are computed lazily.
        for seat, students in self.grouped_by_seat.items():
            self.seat_state_cache[seat] = self.compute_seat_state(students)

        # self.render_room(self.room_filter_var.get())
        selected = (self.room_filter_var.get() or "ALL").upper()

        if selected == "ALL":
            self.render_all_rooms_grouped()
        else:
            self.render_room(selected)

    def render_all_rooms_grouped(self):

        rooms = ["A", "B", "C"]

        # ----------------------------------
        # Gather room information
        # ----------------------------------

        room_info = {}

        for room in rooms:

            layout = self.layout_cache.get(room) or (5, 5, 8)

            _, columns, seat_spacing = layout

            columns = max(1, int(columns))
            seat_spacing = max(0, int(seat_spacing))

            room_seats = [
                r["seat_number"]
                for r in self.seats_cache
                if (r["room"] or "A").strip().upper() == room
            ]

            room_info[room] = {
                "columns": columns,
                "seat_spacing": seat_spacing,
                "seats": room_seats,
            }

        # ----------------------------------
        # Decide layout rows
        # ----------------------------------

        layout_rows = []

        all_three_small = all(room_info[r]["columns"] <= 3 for r in rooms)

        if all_three_small:

            layout_rows.append(["A", "B", "C"])

        else:

            i = 0

            while i < len(rooms):

                room = rooms[i]
                cols = room_info[room]["columns"]

                if i < len(rooms) - 1:

                    next_room = rooms[i + 1]
                    next_cols = room_info[next_room]["columns"]

                    if 4 <= cols <= 6 and 4 <= next_cols <= 6:

                        layout_rows.append([room, next_room])

                        i += 2
                        continue

                layout_rows.append([room])
                i += 1

        # ----------------------------------
        # Render rows
        # ----------------------------------

        for row_rooms in layout_rows:

            row_frame = tk.Frame(
                self.tiles_container,
                bg=COLORS["bg"],
            )

            row_frame.pack(
                fill="x",
                padx=5,
                pady=5,
            )

            for room in row_rooms:

                info = room_info[room]

                columns = info["columns"]
                seat_spacing = info["seat_spacing"]
                room_seats = info["seats"]

                room_card = tk.Frame(
                    row_frame,
                    bg=COLORS["card_bg"],
                    bd=1,
                    relief="solid",
                )

                room_card.pack(
                    side="left",
                    fill="both",
                    expand=True,
                    padx=5,
                    pady=5,
                )

                # ----------------------------
                # Header
                # ----------------------------

                tk.Label(
                    room_card,
                    text=f"🏢 Room {room}",
                    font=FONT_HEADER,
                    bg=COLORS["card_bg"],
                    fg=COLORS["text_primary"],
                ).pack(
                    anchor="w",
                    padx=10,
                    pady=(10, 2),
                )

                tk.Label(
                    room_card,
                    text=f"{len(room_seats)} Seats • {columns} Columns",
                    font=FONT_BODY,
                    bg=COLORS["card_bg"],
                    fg=COLORS["text_secondary"],
                ).pack(
                    anchor="w",
                    padx=10,
                    pady=(0, 10),
                )

                # ----------------------------
                # No seats
                # ----------------------------

                if not room_seats:

                    tk.Label(
                        room_card,
                        text="No seats in this room",
                        font=FONT_BODY,
                        bg=COLORS["card_bg"],
                        fg=COLORS["text_secondary"],
                    ).pack(
                        padx=10,
                        pady=10,
                    )

                    continue

                seats_frame = tk.Frame(
                    room_card,
                    bg=COLORS["card_bg"],
                )

                seats_frame.pack(
                    fill="x",
                    padx=10,
                    pady=(0, 10),
                )

                for c in range(columns):
                    seats_frame.grid_columnconfigure(
                        c,
                        weight=1,
                    )

                # ----------------------------
                # Compact buttons for
                # narrow cards
                # ----------------------------

                if len(row_rooms) >= 2:
                    btn_padx = 8
                    btn_pady = 6
                else:
                    btn_padx = 12
                    btn_pady = 10

                # ----------------------------
                # Seat rendering
                # ----------------------------

                for i, seat in enumerate(
                    sorted(
                        room_seats,
                        key=self._seat_sort_key,
                    )
                ):

                    state = self.seat_state_cache.get(seat)

                    if state is None:
                        state = self.compute_seat_state(
                            self.get_students_for_seat(seat)
                        )

                    btn = tk.Button(
                        seats_frame,
                        text=seat,
                        bg=state["color"],
                        fg="#FFFFFF",
                        activebackground=state["color"],
                        relief="flat",
                        font=FONT_BODY,
                        padx=btn_padx,
                        pady=btn_pady,
                        command=lambda sid=seat: self.on_click(sid),
                    )

                    btn.grid(
                        row=i // columns,
                        column=i % columns,
                        padx=seat_spacing,
                        pady=seat_spacing,
                        sticky="nsew",
                    )

                    btn.bind(
                        "<Enter>",
                        lambda e, sid=seat: self.on_hover(
                            e,
                            sid,
                        ),
                    )

                    btn.bind(
                        "<Leave>",
                        self._on_leave,
                    )

    def refresh(self):
        # Keep behaviour consistent with other pages: refresh on navigation.
        self.render_all_rooms()

    def _on_leave(self, _event=None):
        self.tooltip.place_forget()

    def on_hover(self, event, seat_id):
        state = self.seat_state_cache.get(seat_id)
        if state is None:
            state = self.compute_seat_state(self.get_students_for_seat(seat_id))
            self.seat_state_cache[seat_id] = state

        # Tooltip STRICT: ONLY names
        tooltip_text = "\n".join(state.get("tooltip", []))
        if not tooltip_text:
            tooltip_text = ""
        self.tooltip.configure(text=tooltip_text)
        # place near cursor
        try:
            x = event.x_root - self.winfo_rootx() + 20
            y = event.y_root - self.winfo_rooty() + 10
            self.tooltip.place(x=x, y=y)
        except Exception:
            pass

    def on_click(self, seat_id):
        students = self.get_students_for_seat(seat_id)

        win = tk.Toplevel(self)
        win.title(f"Seat Details — {seat_id}")
        win.geometry("520x420")
        win.configure(bg=COLORS["card_bg"])

        tk.Label(
            win,
            text=f"Seat {seat_id}",
            font=FONT_HEADER,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            padx=16,
            pady=10,
        ).pack(fill="x")

        body = tk.Frame(win, bg=COLORS["card_bg"], padx=16, pady=16)
        body.pack(fill="both", expand=True)

        if not students:
            tk.Label(
                body,
                text="No active students",
                font=FONT_BODY,
                bg=COLORS["card_bg"],
                fg=COLORS["text_secondary"],
            ).pack(anchor="w")
            return

        # Render each student summary
        for s in students:
            st = s["shift_type"] if "shift_type" in s.keys() else "FULL_DAY"
            st_label = {
                "FULL_DAY": "Full Day",
                "HALF_DAY_DAY": "Half Day (Day)",
                "HALF_DAY_NIGHT": "Half Day (Night)",
            }.get(st, "Full Day")

            due_amount = s["due_amount"] if "due_amount" in s.keys() else 0

            line = tk.Label(
                body,
                text=(
                    f"• {s['full_name']}\n"
                    f"  Shift: {st_label}\n"
                    f"  Mobile: {s['mobile_number']}\n"
                    f"  Fee Due: ₹{float(due_amount):.0f}"
                ),
                font=FONT_BODY,
                bg=COLORS["card_bg"],
                fg=COLORS["text_primary"],
                justify="left",
                anchor="w",
                padx=8,
                pady=8,
            )
            line.pack(fill="x", anchor="w", pady=6)
