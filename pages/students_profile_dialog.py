import os
import tkinter as tk

from config.paths import STUDENT_PHOTOS_DIR
from config.theme import COLORS, FONT_HEADER, FONT_BODY, FONT_SMALL

from widgets.components import action_button


class _NoImageBox(tk.Frame):
    def __init__(self, parent, w=200, h=200):
        super().__init__(parent, bg="#0B1220", width=w, height=h)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            self,
            text="No Image",
            fg="#FFFFFF",
            bg="#0B1220",
            font=FONT_SMALL,
        ).place(relx=0.5, rely=0.5, anchor="center")


class StudentProfileDialog(tk.Toplevel):
    def __init__(self, parent, db, student_id: int):
        super().__init__(parent)
        self.db = db
        self.student_id = student_id
        self.result = None
        self.resizable(False, False)
        self.configure(bg=COLORS["card_bg"])
        self.grab_set()

        self.title("Student Profile")
        self.geometry("560x560")

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 560) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 560) // 2
        self.geometry(f"+{x}+{y}")

        tk.Label(
            self,
            text="Student Profile",
            font=FONT_HEADER,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            padx=20,
            pady=12,
        ).pack(fill="x")

        self.body = tk.Frame(self, bg=COLORS["card_bg"], padx=22, pady=18)
        self.body.pack(fill="both", expand=True)
        self.body.columnconfigure(1, weight=1)

        student = self.db.get_student_by_id(student_id)
        self.student = student
        if not student:
            tk.Label(
                self.body,
                text="Student record not found.",
                font=FONT_BODY,
                bg=COLORS["card_bg"],
                fg=COLORS["text_secondary"],
            ).pack(anchor="w")
            action_button(
                self.body, "Close", self.destroy, color=COLORS["text_secondary"]
            ).pack(fill="x", pady=(18, 0))
            return

        # Photo preview + upload/replace controls
        photo_wrap = tk.Frame(self.body, bg=COLORS["card_bg"])
        photo_wrap.grid(row=0, column=0, columnspan=2, pady=(0, 14), sticky="n")
        photo_wrap.columnconfigure(0, weight=1)

        self._photo_holder = tk.Frame(photo_wrap, bg="#0B1220", width=240, height=240)
        self._photo_holder.pack_propagate(False)
        self._photo_holder.grid(row=0, column=0)

        self._photo_label = tk.Label(
            self._photo_holder,
            bg="#0B1220",
            fg="#FFFFFF",
            text="No Image",
            font=FONT_SMALL,
        )
        self._photo_label.place(relx=0.5, rely=0.5, anchor="center")

        # Neutral controls below the photo box
        self._photo_action_frame = tk.Frame(photo_wrap, bg=COLORS["card_bg"])
        self._photo_action_frame.grid(row=1, column=0, pady=(10, 0))

        self._btn_upload = tk.Button(
            self._photo_action_frame,
            text="▲",
            width=2,
            height=1,
            bg=COLORS["accent2"],
            fg="#FFFFFF",
            font=FONT_SMALL,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._choose_photo_for_profile,
        )

        self._btn_replace = tk.Button(
            self._photo_action_frame,
            text="✏",
            width=2,
            height=1,
            bg=COLORS["accent2"],
            fg="#FFFFFF",
            font=FONT_SMALL,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._choose_photo_for_profile,
        )

        self._tk_photo = None
        self._current_photo_loaded = False
        self._render_photo_from_path()
        self._refresh_photo_action_buttons()

        # Details
        details = [
            ("Seat Number", self._row_get(student, "seat_number")),
            ("Full Name", self._row_get(student, "full_name")),
            ("Mobile Number", self._row_get(student, "mobile_number")),
            ("Admission Date", self._row_get(student, "admission_date")),
            ("Exit Date", self._row_get(student, "exit_date") or "—"),
            ("Status", self._row_get(student, "status")),
            ("Shift Type", self._row_get(student, "shift_type")),
        ]

        r = 1
        for k, v in details:
            tk.Label(
                self.body,
                text=f"{k}:",
                font=FONT_BODY,
                bg=COLORS["card_bg"],
                fg=COLORS["text_secondary"],
                anchor="w",
            ).grid(row=r, column=0, sticky="w", pady=4)
            tk.Label(
                self.body,
                text=str(v) if v is not None else "—",
                font=FONT_BODY,
                bg=COLORS["card_bg"],
                fg=COLORS["text_primary"],
                anchor="w",
                wraplength=480,
                justify="left",
            ).grid(row=r, column=1, sticky="w", pady=4)
            r += 1

        # Close button (read-only)
        action_button(
            self.body, "Close", self.destroy, color=COLORS["text_secondary"]
        ).grid(row=r + 1, column=0, columnspan=2, sticky="ew", pady=(18, 0))

    def _render_photo_from_path(self):
        photo_path = self._row_get(self.student, "photo_path")
        if not photo_path or not os.path.exists(photo_path):
            self._current_photo_loaded = False
            self._refresh_photo_action_buttons()
            return

        try:
            from PIL import Image, ImageTk

            img = Image.open(photo_path)
            img.load()
            img = img.convert("RGBA")
            img.thumbnail((240, 240), Image.Resampling.LANCZOS)

            canvas = Image.new("RGBA", (240, 240), (0, 0, 0, 255))
            x = (240 - img.width) // 2
            y = (240 - img.height) // 2
            canvas.paste(img, (x, y), img)

            self._tk_photo = ImageTk.PhotoImage(canvas)
            self._photo_label.destroy()
            tk.Label(self._photo_holder, image=self._tk_photo, bg="#0B1220").place(
                relx=0.5, rely=0.5, anchor="center"
            )
            self._current_photo_loaded = True
            self._refresh_photo_action_buttons()
        except Exception:
            # corrupted image -> keep placeholder
            self._current_photo_loaded = False
            self._refresh_photo_action_buttons()
            return

    def _refresh_photo_action_buttons(self):
        # Clear current buttons
        for child in self._photo_action_frame.winfo_children():
            child.pack_forget()

        if getattr(self, "_current_photo_loaded", False):
            self._btn_replace.pack(pady=(0, 0))
        else:
            self._btn_upload.pack(pady=(0, 0))

    def _choose_photo_for_profile(self):
        from tkinter import filedialog, messagebox
        from PIL import ImageFile

        ImageFile.LOAD_TRUNCATED_IMAGES = True

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

        # Reuse StudentDialog validation logic
        from student_photo_utils import validate_image_extension

        ok, msg = validate_image_extension(path)
        if not ok:
            messagebox.showerror("Invalid Photo", msg, parent=self)
            return

        # Save using same disk layout as StudentsPage
        from student_photo_utils import (
            ensure_dir,
            make_photo_filenames,
            resize_and_save_photo,
        )

        PHOTO_DIR = str(STUDENT_PHOTOS_DIR)
        ensure_dir(PHOTO_DIR)

        full_name, thumb_name = make_photo_filenames(
            self._row_get(self.student, "full_name", "Student"),
            self._row_get(self.student, "seat_number", "00"),
            self._row_get(self.student, "mobile_number", "0000000000"),
            path,
            photo_dir=PHOTO_DIR,
        )
        full_path = os.path.join(PHOTO_DIR, full_name)
        thumb_path = os.path.join(PHOTO_DIR, thumb_name)
        try:
            resize_and_save_photo(path, full_path, thumb_path)
        except Exception as exc:
            messagebox.showerror(
                "Invalid Photo",
                f"The selected image could not be processed.\n{exc}",
                parent=self,
            )
            return

        # Update DB reference (keeps photo permanently linked to this student id)
        self.db.set_student_photo_path(self.student_id, full_path)
        self.student = self.db.get_student_by_id(self.student_id)

        # Re-render
        self._photo_label = tk.Label(
            self._photo_holder,
            bg="#0B1220",
            fg="#FFFFFF",
            text="No Image",
            font=FONT_SMALL,
        )
        self._photo_label.place(relx=0.5, rely=0.5, anchor="center")
        self._render_photo_from_path()

    def _row_get(self, row, key, default=None):
        if not row:
            return default
        try:
            return row[key]
        except Exception:
            return default
