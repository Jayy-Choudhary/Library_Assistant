from __future__ import annotations

from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from config.theme import (
    COLORS,
    FONT_HEADER,
    FONT_BODY,
    FONT_SMALL,
)
from database.database import Database
from widgets.components import label_entry, action_button

import os
from PIL import Image, ImageTk


from student_photo_utils import (
    validate_image_extension,
)


class BaseDialog(tk.Toplevel):

    def __init__(
        self, parent: tk.Misc, title: str, width: int = 480, height: int = 420
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.configure(bg=COLORS["card_bg"])
        self.grab_set()
        self.result = None

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        self.geometry(f"+{x}+{y}")

        tk.Label(
            self,
            text=title,
            font=FONT_HEADER,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            padx=20,
            pady=12,
        ).pack(fill="x")

        self.body_frame = tk.Frame(self, bg=COLORS["card_bg"], padx=24, pady=16)
        self.body_frame.pack(fill="both", expand=True)

        self._build_body()
        self._build_buttons()

    def _build_body(self):
        pass

    def _build_buttons(self):
        bf = tk.Frame(self, bg=COLORS["card_bg"], pady=12)
        bf.pack(fill="x", padx=24)
        action_button(bf, "Confirm", self._on_confirm, color=COLORS["accent"]).pack(
            side="left", padx=4
        )
        action_button(
            bf,
            "Cancel",
            self.destroy,
            color=COLORS["text_secondary"],
        ).pack(side="left", padx=4)

    def _on_confirm(self):
        self.result = self._collect()
        if self.result is not None:
            self.destroy()

    def _collect(self):
        return {}


class StudentDialog(BaseDialog):

    def __init__(
        self,
        parent: tk.Misc,
        db: Database,
        student=None,
        fee=None,
    ):
        self.db = db
        self.student = student
        self.fee = fee
        self.selected_photo_path = None
        self.remove_photo_requested = False
        self._photo_preview_image = None
        title = "Edit Student" if student else "Add New Student"
        super().__init__(parent, title, 520, 720)

    def _photo_placeholder(self, parent, w=180, h=180):
        ph = tk.Frame(parent, bg="#0B1220", width=w, height=h)
        ph.grid_propagate(False)
        tk.Label(
            ph,
            text="No Image",
            fg="#FFFFFF",
            bg="#0B1220",
            font=FONT_SMALL,
        ).place(relx=0.5, rely=0.5, anchor="center")
        return ph

    def _load_photo_to_preview(self, photo_path: str, size=(180, 180)):
        if not photo_path:
            return None
        if not os.path.exists(photo_path):
            return None

        try:
            img = Image.open(photo_path)
            img.load()
            img = img.convert("RGBA")
            img.thumbnail(size, Image.Resampling.LANCZOS)

            canvas = Image.new("RGBA", size, (0, 0, 0, 255))
            x = (size[0] - img.width) // 2
            y = (size[1] - img.height) // 2
            canvas.paste(img, (x, y), img)

            return ImageTk.PhotoImage(canvas)
        except Exception:
            return None

    def _build_body(self):
        bf = self.body_frame
        bf.columnconfigure(1, weight=1)

        # Shift Type (top)
        tk.Label(
            bf,
            text="Shift Type",
            font=FONT_BODY,
            bg=COLORS["card_bg"],
            fg=COLORS["text_primary"],
        ).grid(row=0, column=0, sticky="w", pady=6, padx=(0, 16))

        # For Add: defaults to FULL_DAY unless editing.
        shift_default = (
            self._row_get(self.student, "shift_type", "FULL_DAY")
            if self.student
            else "FULL_DAY"
        )

        self.shift_map = {
            "FULL_DAY": "Full Day",
            "HALF_DAY_DAY": "Half Day (Day)",
            "HALF_DAY_NIGHT": "Half Day (Night)",
        }
        self.reverse_shift_map = {v: k for k, v in self.shift_map.items()}

        self.shift_var = tk.StringVar()
        # Initialize shift UI
        self.shift_var.set(self.shift_map.get(shift_default, "Full Day"))

        shift_cb = ttk.Combobox(
            bf,
            textvariable=self.shift_var,
            values=["Full Day", "Half Day (Day)", "Half Day (Night)"],
            state="readonly",
            font=FONT_BODY,
            width=26,
        )
        shift_cb.grid(row=0, column=1, sticky="ew", pady=6)

        # Seat Number (below; populated after shift selection)
        # (Important: label must use the same column/row as the combobox)
        tk.Label(
            bf,
            text="Seat Number",
            font=FONT_BODY,
            bg=COLORS["card_bg"],
            fg=COLORS["text_primary"],
        ).grid(row=1, column=0, sticky="w", pady=6, padx=(0, 16))

        self.seat_var = tk.StringVar()
        # Initially empty for Add; for Edit prefill and allow it in case it belongs.
        initial_seats = []
        if self.student:
            # Ensure the existing seat remains selectable for the stored shift.
            initial_seats = self.db.get_compatible_seats(shift_default)
            if self.student["seat_number"] not in initial_seats:
                initial_seats.insert(0, self.student["seat_number"])
            self.seat_var.set(self.student["seat_number"])

        self.seat_cb = ttk.Combobox(
            bf,
            textvariable=self.seat_var,
            values=initial_seats,
            state="readonly" if (self.student or initial_seats) else "disabled",
            font=FONT_BODY,
            width=26,
        )
        self.seat_cb.grid(row=1, column=1, sticky="ew", pady=6)

        # NOTE: labels created by label_entry() use row indices.
        # Since Seat/Shift are now rows 0-1, move the rest down.
        self.name_var, _ = label_entry(
            bf, "Full Name", 2, self.student["full_name"] if self.student else ""
        )
        self.mob_var, _ = label_entry(
            bf,
            "Mobile Number",
            3,
            self.student["mobile_number"] if self.student else "",
        )
        self.adm_var, _ = label_entry(
            bf,
            "Admission Date (YYYY-MM-DD)",
            4,
            self.student["admission_date"] if self.student else str(date.today()),
        )

        fee_val = str(int(self.fee["monthly_fee"])) if self.fee else "0"
        self.fee_var, _ = label_entry(bf, "Monthly Fee (₹)", 5, fee_val)

        tk.Label(
            bf,
            text="Student Photo",
            font=FONT_BODY,
            bg=COLORS["card_bg"],
            fg=COLORS["text_primary"],
        ).grid(row=6, column=0, sticky="nw", pady=(12, 6), padx=(0, 16))

        photo_area = tk.Frame(bf, bg=COLORS["card_bg"])
        photo_area.grid(row=6, column=1, sticky="w", pady=(12, 6))

        self.photo_preview = tk.Frame(photo_area, bg="#0B1220", width=140, height=140)
        self.photo_preview.pack_propagate(False)
        self.photo_preview.pack(side="left")

        photo_buttons = tk.Frame(photo_area, bg=COLORS["card_bg"])
        photo_buttons.pack(side="left", padx=(12, 0), anchor="n")
        # Icon square buttons (upload / remove)
        upload_btn = tk.Button(
            photo_buttons,
            text="▲",
            command=self._choose_photo,
            width=2,
            height=1,
            bg=COLORS["accent2"],
            fg="#FFFFFF",
            font=FONT_SMALL,
            relief="flat",
            bd=0,
            cursor="hand2",
        )
        upload_btn.pack(side="top", pady=(0, 6))

        remove_btn = tk.Button(
            photo_buttons,
            text="✖",
            command=self._remove_photo,
            width=2,
            height=1,
            bg=COLORS["danger"],
            fg="#FFFFFF",
            font=FONT_SMALL,
            relief="flat",
            bd=0,
            cursor="hand2",
        )
        remove_btn.pack(side="top")

        current_photo = self._row_get(self.student, "photo_path")
        self._render_photo_preview(current_photo)

        # Initialize seat dropdown based on current shift selection.
        def _refresh_seats_on_shift_change():
            selected_label = self.shift_var.get()
            target_shift = self.reverse_shift_map.get(selected_label, "FULL_DAY")
            new_seats = self.db.get_compatible_seats(target_shift)

            current = self.seat_var.get().strip()
            # In edit mode, keep the current seat even if it’s not in the default list.
            if self.student and current and current not in new_seats:
                new_seats.insert(0, current)

            self.seat_cb.configure(values=new_seats)
            self.seat_cb.configure(state="readonly" if new_seats else "disabled")

            if current in new_seats:
                self.seat_var.set(current)
            elif new_seats:
                self.seat_var.set(new_seats[0])
            else:
                self.seat_var.set("")

        _refresh_seats_on_shift_change()

        shift_cb.bind(
            "<<ComboboxSelected>>", lambda _e: _refresh_seats_on_shift_change()
        )

    def _row_get(self, row, key, default=None):
        if not row:
            return default
        try:
            return row[key]
        except Exception:
            return default

    def _clear_photo_preview(self):
        for child in self.photo_preview.winfo_children():
            child.destroy()
        self._photo_preview_image = None

    def _render_photo_preview(self, photo_path=None):
        self._clear_photo_preview()
        img = self._load_photo_to_preview(photo_path, size=(140, 140))
        if img is None:
            tk.Label(
                self.photo_preview,
                text="No Image",
                fg="#FFFFFF",
                bg="#0B1220",
                font=FONT_SMALL,
            ).place(relx=0.5, rely=0.5, anchor="center")
            return

        self._photo_preview_image = img
        tk.Label(
            self.photo_preview, image=self._photo_preview_image, bg="#0B1220"
        ).place(relx=0.5, rely=0.5, anchor="center")

    def _choose_photo(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Choose Student Photo",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        ok, msg = validate_image_extension(path)
        if not ok:
            messagebox.showerror("Invalid Photo", msg, parent=self)
            return

        preview = self._load_photo_to_preview(path, size=(140, 140))
        if preview is None:
            messagebox.showerror(
                "Invalid Photo",
                "The selected image could not be read.",
                parent=self,
            )
            return

        self.selected_photo_path = path
        self.remove_photo_requested = False
        self._render_photo_preview(path)

    def _remove_photo(self):
        self.selected_photo_path = None
        self.remove_photo_requested = True
        self._render_photo_preview(None)

    def _collect(self):
        seat = self.seat_var.get().strip()
        name = self.name_var.get().strip()
        mob = self.mob_var.get().strip()
        adm = self.adm_var.get().strip()
        fee_s = self.fee_var.get().strip()

        if not seat:
            messagebox.showerror("Error", "Select a seat.", parent=self)
            return None
        if not name:
            messagebox.showerror("Error", "Enter full name.", parent=self)
            return None
        if not (mob.isdigit() and len(mob) == 10):
            messagebox.showerror("Error", "Mobile must be 10 digits.", parent=self)
            return None

        try:
            datetime.strptime(adm, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror(
                "Error", "Admission date format: YYYY-MM-DD", parent=self
            )
            return None

        try:
            fee_val = float(fee_s)
        except ValueError:
            messagebox.showerror("Error", "Monthly fee must be a number.", parent=self)
            return None

        shift_map = {
            "Full Day": "FULL_DAY",
            "Half Day (Day)": "HALF_DAY_DAY",
            "Half Day (Night)": "HALF_DAY_NIGHT",
        }

        return {
            "seat": seat,
            "name": name,
            "mobile": mob,
            "admission": adm,
            "monthly_fee": fee_val,
            "shift_type": self.reverse_shift_map.get(self.shift_var.get(), "FULL_DAY"),
            "photo_source": self.selected_photo_path,
            "remove_photo": self.remove_photo_requested,
        }


class OldStudentDialog(BaseDialog):
    def __init__(self, parent: tk.Misc):
        super().__init__(parent, "Mark as Old Student", 420, 280)

    def _build_body(self):
        self.exit_var, _ = label_entry(
            self.body_frame, "Exit Date (YYYY-MM-DD)", 0, str(date.today())
        )

        tk.Label(
            self.body_frame,
            text="The seat will be freed and status updated.",
            font=FONT_SMALL,
            bg=COLORS["card_bg"],
            fg=COLORS["text_secondary"],
            wraplength=380,
        ).grid(row=1, column=0, columnspan=2, pady=10, sticky="w")

    def _collect(self):
        dt = self.exit_var.get().strip()
        try:
            datetime.strptime(dt, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Date format: YYYY-MM-DD", parent=self)
            return None
        return {"exit_date": dt}


class PaymentDialog(BaseDialog):
    def __init__(
        self,
        parent: tk.Misc,
        student_name: str,
        current_due: float,
    ):
        self.student_name = student_name
        self.current_due = current_due
        super().__init__(parent, f"Record Payment — {student_name}", 440, 320)

    def _build_body(self):
        bf = self.body_frame
        tk.Label(
            bf,
            text=f"Current Due: ₹{self.current_due:.0f}",
            font=FONT_HEADER,
            bg=COLORS["card_bg"],
            fg=COLORS["danger"],
        ).grid(row=0, column=0, columnspan=2, pady=(0, 12), sticky="w")

        self.amt_var, _ = label_entry(
            bf,
            "Amount Paid (₹)",
            1,
            str(int(self.current_due)),
        )
        self.date_var, _ = label_entry(
            bf,
            "Payment Date (YYYY-MM-DD)",
            2,
            str(date.today()),
        )
        self.note_var, _ = label_entry(
            bf,
            "Notes (optional)",
            3,
            "",
        )

    def _collect(self):
        try:
            amt = float(self.amt_var.get())
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number.", parent=self)
            return None
        if amt <= 0:
            messagebox.showerror("Error", "Amount must be > 0.", parent=self)
            return None

        dt = self.date_var.get().strip()
        try:
            datetime.strptime(dt, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Date format: YYYY-MM-DD", parent=self)
            return None

        return {"amount": amt, "date": dt, "notes": self.note_var.get().strip()}


class FeeUpdateDialog(BaseDialog):
    def __init__(
        self,
        parent: tk.Misc,
        student_name: str,
        current_fee: float,
        current_due: float,
    ):
        self.student_name = student_name
        self.current_fee = current_fee
        self.current_due = current_due
        super().__init__(parent, f"Update Fee — {student_name}", 440, 340)

    def _build_body(self):
        bf = self.body_frame
        self.fee_var, _ = label_entry(
            bf, "Monthly Fee (₹)", 0, str(int(self.current_fee))
        )
        self.due_var, _ = label_entry(
            bf, "Current Due (₹)", 1, str(int(self.current_due))
        )

        tk.Label(
            bf,
            text="You can also manually adjust the due amount here.",
            font=FONT_SMALL,
            bg=COLORS["card_bg"],
            fg=COLORS["text_secondary"],
            wraplength=380,
        ).grid(row=2, column=0, columnspan=2, pady=8, sticky="w")

    def _collect(self):
        try:
            fee = float(self.fee_var.get())
            due = float(self.due_var.get())
        except ValueError:
            messagebox.showerror("Error", "Values must be numbers.", parent=self)
            return None
        return {"monthly_fee": fee, "due_amount": due}


class RoomLayoutDialog(BaseDialog):
    def __init__(self, parent: tk.Misc, db: Database, room: str):
        self.db = db
        self.room = (room or "A").strip().upper()
        if self.room not in ("A", "B", "C"):
            self.room = "A"

        super().__init__(parent, "Room Layout", 520, 420)

    def _build_body(self):
        bf = self.body_frame
        bf.columnconfigure(1, weight=1)

        tk.Label(
            bf,
            text="Room",
            font=FONT_BODY,
            bg=COLORS["card_bg"],
            fg=COLORS["text_primary"],
        ).grid(row=0, column=0, sticky="w", pady=6, padx=(0, 16))

        self.room_var = tk.StringVar(value=self.room)
        room_frame = tk.Frame(bf, bg=COLORS["card_bg"])
        room_frame.grid(row=0, column=1, sticky="w", pady=6)
        for r in ("A", "B", "C"):
            tk.Radiobutton(
                room_frame,
                text=r,
                variable=self.room_var,
                value=r,
                bg=COLORS["card_bg"],
                fg=COLORS["text_primary"],
                activebackground=COLORS["card_bg"],
                activeforeground=COLORS["text_primary"],
                command=self._on_room_change,
            ).pack(side="left", padx=10)

        self.rows_var, self.rows_entry = label_entry(bf, "Rows", 1, "5", width=260)
        self.cols_var, self.cols_entry = label_entry(bf, "Columns", 2, "5", width=260)
        self.spacing_var, self.spacing_entry = label_entry(
            bf, "Seat Spacing", 3, "8", width=260
        )

        # Set initial values from DB
        rows, cols, spacing = self.db.get_room_layout(self.room_var.get())
        self.rows_var.set(str(rows))
        self.cols_var.set(str(cols))
        self.spacing_var.set(str(spacing))

        self.seats_count_lbl = tk.Label(
            bf,
            text="Seats in room: -",
            font=FONT_BODY,
            bg=COLORS["card_bg"],
            fg=COLORS["text_secondary"],
        )
        self.seats_count_lbl.grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(16, 6)
        )

        self.capacity_lbl = tk.Label(
            bf,
            text="Capacity: -",
            font=FONT_BODY,
            bg=COLORS["card_bg"],
            fg=COLORS["text_secondary"],
        )
        self.capacity_lbl.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 6))

        # Live update
        for var in (self.rows_var, self.cols_var):

            def _cb(*_):
                self._update_capacity_preview()

            var.trace_add("write", _cb)

        self._on_room_change()

    def _on_room_change(self):
        room = self.room_var.get().strip().upper()
        if room not in ("A", "B", "C"):
            room = "A"
            self.room_var.set(room)

        rows, cols, spacing = self.db.get_room_layout(room)
        self.rows_var.set(str(rows))
        self.cols_var.set(str(cols))
        self.spacing_var.set(str(spacing))

        seat_count = len(self.db.get_seats_by_room(room))
        self.seats_count_lbl.configure(text=f"Seats in room: {seat_count}")
        self._update_capacity_preview()

    def _update_capacity_preview(self):
        try:
            rows = int(self.rows_var.get())
        except ValueError:
            rows = 0
        try:
            cols = int(self.cols_var.get())
        except ValueError:
            cols = 0
        cap = rows * cols
        self.capacity_lbl.configure(text=f"Capacity: {cap}")

    def _collect(self):
        room = self.room_var.get().strip().upper()
        if room not in ("A", "B", "C"):
            messagebox.showerror("Error", "Invalid room.", parent=self)
            return None

        try:
            rows = int(self.rows_var.get())
            cols = int(self.cols_var.get())
            spacing = int(self.spacing_var.get())
        except ValueError:
            messagebox.showerror(
                "Error",
                "Rows, Columns, and Seat Spacing must be integers.",
                parent=self,
            )
            return None

        if not (1 <= rows <= 50):
            messagebox.showerror("Error", "Rows must be between 1 and 50.", parent=self)
            return None
        if not (1 <= cols <= 50):
            messagebox.showerror(
                "Error", "Columns must be between 1 and 50.", parent=self
            )
            return None
        if not (0 <= spacing <= 100):
            messagebox.showerror(
                "Error", "Seat Spacing must be between 0 and 100.", parent=self
            )
            return None

        seat_count = len(self.db.get_seats_by_room(room))
        capacity = rows * cols
        if capacity < seat_count:
            messagebox.showerror(
                "Error",
                "Layout capacity is smaller than the number of seats in this room.",
                parent=self,
            )
            return None

        return {"room": room, "rows": rows, "columns": cols, "seat_spacing": spacing}


class AddSeatsDialog(BaseDialog):
    def __init__(self, parent: tk.Misc):
        super().__init__(parent, "Add Seats", 420, 360)

    def _build_body(self):
        bf = self.body_frame
        tk.Label(
            bf,
            text="Generate seats like A01–A50",
            font=FONT_SMALL,
            fg=COLORS["text_secondary"],
            bg=COLORS["card_bg"],
        ).grid(row=0, columnspan=2, sticky="w", pady=(0, 10))

        self.prefix_var, _ = label_entry(bf, "Prefix (e.g. A)", 1, "A")
        self.start_var, _ = label_entry(bf, "Start Number", 2, "1")
        self.end_var, _ = label_entry(bf, "End Number", 3, "10")

        tk.Label(
            bf,
            text="Room",
            font=FONT_SMALL,
            bg=COLORS["card_bg"],
            fg=COLORS["text_secondary"],
        ).grid(row=4, column=0, sticky="w", pady=(14, 4))

        self.room_var = tk.StringVar(value="A")
        room_frame = tk.Frame(bf, bg=COLORS["card_bg"])
        room_frame.grid(row=4, column=1, sticky="w", pady=(14, 4))
        for r in ("A", "B", "C"):
            tk.Radiobutton(
                room_frame,
                text=r,
                variable=self.room_var,
                value=r,
                bg=COLORS["card_bg"],
                fg=COLORS["text_primary"],
                activebackground=COLORS["card_bg"],
                activeforeground=COLORS["text_primary"],
            ).pack(side="left", padx=8)

    def _collect(self):
        prefix = self.prefix_var.get().strip()
        try:
            start = int(self.start_var.get())
            end = int(self.end_var.get())
        except ValueError:
            messagebox.showerror("Error", "Start/End must be integers.", parent=self)
            return None

        if not prefix:
            messagebox.showerror("Error", "Prefix is required.", parent=self)
            return None
        if start > end or start < 1:
            messagebox.showerror("Error", "Invalid range.", parent=self)
            return None

        room = (self.room_var.get() or "A").strip().upper()
        if room not in ("A", "B", "C"):
            room = "A"

        return {"prefix": prefix, "start": start, "end": end, "room": room}
