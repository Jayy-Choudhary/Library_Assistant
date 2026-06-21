import os
import tkinter as tk

from tkinter import messagebox, filedialog

from config.paths import STUDENT_PHOTOS_DIR
from config.theme import COLORS, FONT_BODY, FONT_SMALL
from dialogs import StudentDialog, OldStudentDialog
from pages.students_profile_dialog import StudentProfileDialog
from student_photo_utils import (
    ensure_dir,
    make_photo_filenames,
    resize_and_save_photo,
    validate_image_extension,
)

from widgets.components import styled_treeview, action_button

from .page_base import PageBase


class StudentsPage(PageBase):
    PHOTO_DIR = str(STUDENT_PHOTOS_DIR)

    def __init__(self, parent, db):
        self._thumb_cache = {}
        self._thumb_cache_cap = 120
        self._hover_over_fullname = False
        self._hover_row_id = None
        self._hover_thumb_label = None
        self._hover_thumb_photo = None
        self._info_photo_image = None
        self._info_student_id = None
        super().__init__(parent, db)

    def _build(self):
        self._section_header("🎓  Students")
        self._divider()

        # Two-panel layout: left table, right permanent information panel
        container = tk.Frame(self, bg=COLORS["bg"])
        container.pack(fill="both", expand=True, padx=28, pady=(4, 20))
        container.columnconfigure(0, weight=3)
        container.columnconfigure(1, weight=0)

        # Right panel fixed width
        self.info_panel_width = 320

        # Toolbar
        tb = tk.Frame(container, bg=COLORS["bg"])
        tb.grid(row=0, column=0, columnspan=2, sticky="ew")
        tb.grid_columnconfigure(0, weight=1)

        action_button(tb, "+ Add Student", self._add_student).pack(side="left", padx=4)
        action_button(tb, "✏  Edit", self._edit_student, color="#0EA5E9").pack(
            side="left", padx=4
        )
        action_button(tb, "🔴 Mark Old", self._mark_old, color=COLORS["warning"]).pack(
            side="left", padx=4
        )
        action_button(
            tb, "📤 Export CSV", self._export_csv, color=COLORS["success"]
        ).pack(side="left", padx=4)

        # Search
        tk.Label(
            tb,
            text="Search:",
            font=FONT_BODY,
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"],
        ).pack(side="left", padx=(20, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._search())
        tk.Entry(
            tb,
            textvariable=self.search_var,
            font=FONT_BODY,
            width=22,
            bg="#F9FAFB",
            relief="flat",
            bd=6,
        ).pack(side="left", padx=4)

        # Filter
        self.filter_var = tk.StringVar(value="Active")
        for val in ("All", "Active", "Old Student"):
            tk.Radiobutton(
                tb,
                text=val,
                variable=self.filter_var,
                value=val,
                font=FONT_SMALL,
                bg=COLORS["bg"],
                fg=COLORS["text_primary"],
                activebackground=COLORS["bg"],
                command=self.refresh,
            ).pack(side="left", padx=4)

        # Table (simplified columns)
        cols = [
            "Seat No.",
            "Full Name",
            "Admission Date",
            "Exit Date",
        ]
        widths = {
            "Seat No.": 120,
            "Full Name": 260,
            "Admission Date": 160,
            "Exit Date": 160,
        }
        tframe, self.tree = styled_treeview(container, cols, widths, height=20)
        tframe.grid(row=1, column=0, sticky="nsew", padx=18, pady=(4, 20))
        container.grid_rowconfigure(1, weight=1)

        # Selection -> update right info panel
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<ButtonRelease-1>", lambda _e: self._on_tree_select())
        # Double-click neutralized (was opening StudentProfileDialog)
        self.tree.bind("<Double-1>", lambda _e: None)

        # Hover photo preview (neutralized)
        self.tree.bind("<Motion>", lambda _e: None)
        self.tree.bind("<Leave>", lambda _e: None)

        # Build the right-side info panel inside the same container
        self._build_info_panel(container)

        # Right panel should show placeholders until selection happens
        self._update_info_panel(None)

        self.refresh()

    def _on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            self._update_info_panel(None)
            return
        try:
            sid = int(sel[0])
        except Exception:
            self._update_info_panel(None)
            return
        self._update_info_panel(sid)
        try:
            self.update_idletasks()
        except Exception:
            pass

    def _update_info_panel(self, student_id: int | None):
        student = None
        self._info_student_id = student_id
        if student_id is not None:
            student = self.db.get_student_by_id(student_id)
        if not student:
            self._info_student_id = None
            self._render_info_photo(None)
            self._set_info_field(self.name_var, "-")
            self._set_info_field(self.seat_var, "-")
            self._set_info_field(self.shift_var, "-")
            self._set_info_field(self.mobile_var, "-")
            self._set_info_field(self.adm_var, "-")
            self._set_info_field(self.monthly_fee_var, "-")
            self._set_info_field(self.due_var, "-")
            self._set_info_field(self.status_var, "-")
            return

        # Load fee + derived due
        fee = self.db.get_fee_record(student_id)
        due_amount = fee["due_amount"] if fee else None

        self._render_info_photo(self._row_get(student, "photo_path"), student_id)
        self._set_info_field(
            self.name_var, self._row_get(student, "full_name", "-") or "-"
        )
        self._set_info_field(
            self.seat_var, self._row_get(student, "seat_number", "-") or "-"
        )
        self._set_info_field(
            self.shift_var, self._row_get(student, "shift_type", "-") or "-"
        )
        self._set_info_field(
            self.mobile_var, self._row_get(student, "mobile_number", "-") or "-"
        )
        self._set_info_field(
            self.adm_var, self._row_get(student, "admission_date", "-") or "-"
        )
        self._set_info_field(
            self.monthly_fee_var,
            (
                f"₹{float(fee['monthly_fee']):.0f}"
                if fee and self._row_get(fee, "monthly_fee") is not None
                else "-"
            ),
        )
        self._set_info_field(
            self.due_var,
            f"₹{float(due_amount):.0f}" if due_amount is not None else "-",
        )
        self._set_info_field(
            self.status_var, self._row_get(student, "status", "-") or "-"
        )

    def _row_get(self, row, key, default=None):
        if not row:
            return default
        try:
            return row[key]
        except Exception:
            return default

    def _set_info_field(self, var, value: str):
        var.set(value)

    def _build_info_panel(self, parent=None):

        # Fixed-width right info panel
        parent = parent or self
        panel = tk.Frame(parent, bg=COLORS["card_bg"], width=self.info_panel_width)
        panel.grid(row=1, column=1, sticky="nsw")

        panel.grid_propagate(False)

        header = tk.Label(
            panel,
            text="Student Information",
            font=("Georgia", 16, "bold"),
            bg=COLORS["card_bg"],
            fg=COLORS["text_primary"],
        )
        header.pack(fill="x", padx=16, pady=(18, 10))

        photo = tk.Frame(panel, bg="#0B1220", width=240, height=180)
        photo.pack_propagate(False)
        photo.pack(padx=20, pady=(0, 14))

        # Fields
        fields = [
            ("Name:", "name"),
            ("Seat Number:", "seat"),
            ("Shift:", "shift"),
            ("Mobile Number:", "mobile"),
            ("Admission Date:", "adm"),
            ("Monthly Fee:", "monthly"),
            ("Amount Due:", "due"),
            ("Status:", "status"),
        ]

        form = tk.Frame(panel, bg=COLORS["card_bg"])
        form.pack(fill="x", padx=16)

        self.name_var = tk.StringVar(value="-")
        self.seat_var = tk.StringVar(value="-")
        self.shift_var = tk.StringVar(value="-")
        self.mobile_var = tk.StringVar(value="-")
        self.adm_var = tk.StringVar(value="-")
        self.monthly_fee_var = tk.StringVar(value="-")
        self.due_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value="-")

        values_map = {
            "name": self.name_var,
            "seat": self.seat_var,
            "shift": self.shift_var,
            "mobile": self.mobile_var,
            "adm": self.adm_var,
            "monthly": self.monthly_fee_var,
            "due": self.due_var,
            "status": self.status_var,
        }

        for i, (lbl, key) in enumerate(fields):
            tk.Label(
                form,
                text=lbl,
                font=FONT_SMALL,
                bg=COLORS["card_bg"],
                fg=COLORS["text_secondary"],
                anchor="w",
            ).grid(row=i, column=0, sticky="w", pady=4)
            tk.Label(
                form,
                textvariable=values_map[key],
                font=FONT_BODY,
                bg=COLORS["card_bg"],
                fg=COLORS["text_primary"],
                anchor="w",
                wraplength=self.info_panel_width - 60,
                justify="left",
            ).grid(row=i, column=1, sticky="w", pady=4)

        self._info_panel = panel
        self._info_photo = photo
        self._render_info_photo(None)

    def _clear_info_photo(self):
        for child in self._info_photo.winfo_children():
            child.destroy()
        self._info_photo_image = None

    def _icon_photo_button(self, parent, text, command, color):
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=2,
            height=2 if "\n" in text else 1,
            bg=color,
            fg="#FFFFFF",
            font=FONT_SMALL,
            relief="flat",
            bd=0,
            cursor="hand2",
            activebackground=color,
            activeforeground="#FFFFFF",
        )

    def _render_info_photo(self, photo_path, student_id=None):
        self._clear_info_photo()
        photo = self._load_photo_image(photo_path, (240, 180))
        if photo is None:
            if student_id is None:
                tk.Label(
                    self._info_photo,
                    text="No Image",
                    fg="#FFFFFF",
                    bg="#0B1220",
                    font=FONT_SMALL,
                ).place(relx=0.5, rely=0.5, anchor="center")
                return

            self._icon_photo_button(
                self._info_photo,
                "▲",
                lambda sid=student_id: self._upload_or_replace_info_photo(sid),
                COLORS["accent2"],
            ).place(relx=0.5, rely=0.5, anchor="center")
            return

        self._info_photo_image = photo
        tk.Label(self._info_photo, image=self._info_photo_image, bg="#0B1220").place(
            relx=0.5, rely=0.5, anchor="center"
        )
        if student_id is not None:
            self._icon_photo_button(
                self._info_photo,
                "⇄\n⇄",
                lambda sid=student_id: self._upload_or_replace_info_photo(sid),
                COLORS["accent2"],
            ).place(relx=0.92, rely=0.12, anchor="center")

    def _load_photo_image(self, photo_path, size):
        if not photo_path or not os.path.exists(photo_path):
            return None

        try:
            from PIL import Image, ImageTk

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

    def _populate(self, rows):

        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in rows:
            tag = "old" if r["status"] == "Old Student" else ""
            self.tree.insert(
                "",
                "end",
                iid=str(r["id"]),
                values=(
                    r["seat_number"],
                    r["full_name"],
                    r["admission_date"],
                    r["exit_date"],
                ),
                tags=(tag,),
            )
        self.tree.tag_configure("old", foreground=COLORS["text_secondary"])

    def _on_double_click(self, _event):
        # Open read-only student profile (student_id stored as iid)
        sel = self.tree.selection()
        if not sel:
            return
        try:
            sid = int(sel[0])
        except Exception:
            return
        dlg = StudentProfileDialog(self, self.db, sid)
        self.wait_window(dlg)

    def _get_fullname_col_index(self):
        # Treeview columns are 1-based identifiers
        # With our columns list: Seat No.=#1, Full Name=#2, Mobile Number=#3, ...
        return 2

    def _on_tree_motion(self, event):
        if not event.widget:
            return

        x, y = event.x, event.y
        col = self.tree.identify_column(x)
        # identify_column returns '#1', '#2', ...
        if col != f"#{self._get_fullname_col_index()}":
            self._hide_hover_thumb()
            return

        row_id = self.tree.identify_row(y)
        if not row_id:
            self._hide_hover_thumb()
            return

        # avoid unnecessary work when already showing for same cell
        if self._hover_over_fullname and self._hover_row_id == row_id:
            return

        try:
            sid = int(row_id)
        except Exception:
            self._hide_hover_thumb()
            return

        thumb_photo = self._get_thumbnail_photo(sid)
        self._show_hover_thumb(event, thumb_photo)

        self._hover_over_fullname = True
        self._hover_row_id = row_id

    def _hide_hover_thumb(self, _event=None):
        self._hover_over_fullname = False
        self._hover_row_id = None
        if self._hover_thumb_label is not None:
            try:
                self._hover_thumb_label.destroy()
            except Exception:
                pass
        self._hover_thumb_label = None
        self._hover_thumb_photo = None

    def _get_thumbnail_photo(self, student_id: int):
        # Cache scaled thumbnails keyed by student_id
        if student_id in self._thumb_cache:
            return self._thumb_cache[student_id]

        photo_path = None
        try:
            photo_path = self.db.get_student_photo_path(student_id)
        except Exception:
            photo_path = None

        # We store scaled versions in student_photos/. If thumb exists, use it.
        thumb_photo = None
        try:
            if photo_path:
                # thumb path convention: replace filename suffix _thumb with _thumb already in name
                # Our utils save thumb as the provided thumb filename, so easiest: look for a sibling ending with '_thumb'
                base_dir = os.path.dirname(photo_path)
                # If stored as ..._thumb.ext, accept it; otherwise try compute
                if "_thumb" in os.path.basename(photo_path):
                    thumb_path = photo_path
                else:
                    fn = os.path.basename(photo_path)
                    name, ext = os.path.splitext(fn)
                    thumb_path = os.path.join(base_dir, f"{name}_thumb{ext}")

                if os.path.exists(thumb_path):
                    from PIL import Image, ImageTk

                    img = Image.open(thumb_path)
                    img.load()
                    img = img.convert("RGBA")
                    img.thumbnail((56, 56), Image.Resampling.LANCZOS)
                    canvas = Image.new("RGBA", (56, 56), (0, 0, 0, 255))
                    x = (56 - img.width) // 2
                    y = (56 - img.height) // 2
                    canvas.paste(img, (x, y), img)
                    thumb_photo = ImageTk.PhotoImage(canvas)
        except Exception:
            thumb_photo = None

        # Placeholder thumbnail if missing
        if thumb_photo is None:
            from PIL import Image, ImageTk

            canvas = Image.new("RGBA", (56, 56), (0, 0, 0, 255))
            thumb_photo = ImageTk.PhotoImage(canvas)

        # Cap cache
        if len(self._thumb_cache) >= self._thumb_cache_cap:
            # pop first inserted
            k0 = next(iter(self._thumb_cache.keys()), None)
            if k0 is not None:
                self._thumb_cache.pop(k0, None)
        self._thumb_cache[student_id] = thumb_photo
        return thumb_photo

    def _show_hover_thumb(self, event, thumb_photo):
        # remove existing
        if self._hover_thumb_label is not None:
            try:
                self._hover_thumb_label.destroy()
            except Exception:
                pass

        # create floating label near cursor
        self._hover_thumb_photo = thumb_photo
        x_root = self.tree.winfo_rootx() + event.x
        y_root = self.tree.winfo_rooty() + event.y

        lbl = tk.Label(
            self,
            image=self._hover_thumb_photo,
            bg=COLORS["bg"],
            bd=0,
        )
        lbl.place(x=x_root - self.winfo_rootx() + 6, y=y_root - self.winfo_rooty() + 6)
        self._hover_thumb_label = lbl

    def _save_photo_for_student(self, student_id: int, source_path: str):
        if not source_path:
            return None

        ensure_dir(self.PHOTO_DIR)
        student = self.db.get_student_by_id(student_id)
        full_name, thumb_name = make_photo_filenames(
            self._row_get(student, "full_name", "Student"),
            self._row_get(student, "seat_number", "00"),
            self._row_get(student, "mobile_number", "0000000000"),
            source_path,
            photo_dir=self.PHOTO_DIR,
        )
        full_path = os.path.join(self.PHOTO_DIR, full_name)
        thumb_path = os.path.join(self.PHOTO_DIR, thumb_name)
        resize_and_save_photo(source_path, full_path, thumb_path)
        return full_path

    def _thumb_path_for_photo(self, photo_path: str):
        if not photo_path:
            return None
        base_dir = os.path.dirname(photo_path)
        fn = os.path.basename(photo_path)
        name, ext = os.path.splitext(fn)
        if name.endswith("_thumb"):
            return photo_path
        return os.path.join(base_dir, f"{name}_thumb{ext}")

    def _delete_managed_photo_files(self, photo_path: str):
        if not photo_path:
            return

        managed_dir = os.path.abspath(self.PHOTO_DIR)
        for path in (photo_path, self._thumb_path_for_photo(photo_path)):
            if not path:
                continue
            abs_path = os.path.abspath(path)
            if not abs_path.startswith(managed_dir + os.sep):
                continue
            try:
                if os.path.exists(abs_path):
                    os.remove(abs_path)
            except OSError:
                pass

    def _apply_photo_result(self, student_id: int, dialog_result: dict):
        old_path = self.db.get_student_photo_path(student_id)

        if dialog_result.get("remove_photo"):
            self.db.set_student_photo_path(student_id, None)
            self._delete_managed_photo_files(old_path)
            self._thumb_cache.pop(student_id, None)
            return

        source_path = dialog_result.get("photo_source")
        if not source_path:
            return

        new_path = self._save_photo_for_student(student_id, source_path)
        self.db.set_student_photo_path(student_id, new_path)
        self._delete_managed_photo_files(old_path)
        self._thumb_cache.pop(student_id, None)

    def _upload_or_replace_info_photo(self, student_id: int):
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
            messagebox.showerror("Invalid Photo", msg)
            return

        if self._load_photo_image(path, (240, 180)) is None:
            messagebox.showerror(
                "Invalid Photo",
                "The selected image could not be read.",
            )
            return

        try:
            self._apply_photo_result(
                student_id,
                {"photo_source": path, "remove_photo": False},
            )
        except Exception as exc:
            messagebox.showwarning(
                "Photo Not Saved",
                f"The photo could not be saved:\n{exc}",
            )
            return

        self._update_info_panel(student_id)
        messagebox.showinfo("Photo Updated", "Student photo updated.")

    def refresh(self):
        f = self.filter_var.get()

        if f == "All":
            rows = self.db.get_all_students()
        else:
            rows = self.db.get_all_students(f)
        self._populate(rows)

    def _search(self):
        q = self.search_var.get().strip()
        if q:
            self._populate(self.db.search_students(q))
        else:
            self.refresh()

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a student first.")
            return None
        return int(sel[0])

    def _add_student(self):
        dlg = StudentDialog(self, self.db)
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            result = self.db.add_student(
                d["seat"],
                d["name"],
                d["mobile"],
                d["admission"],
                d["monthly_fee"],
                d.get("shift_type", "FULL_DAY"),
            )
            if isinstance(result, tuple):
                ok, msg = result
                if not ok:
                    messagebox.showerror("Could Not Add Student", msg)
                    return

            student_id = int(result)
            try:
                self._apply_photo_result(student_id, d)
            except Exception as exc:
                messagebox.showwarning(
                    "Photo Not Saved",
                    f"Student was added, but the photo could not be saved:\n{exc}",
                )

            self.refresh()
            messagebox.showinfo(
                "Success", f"Student '{d['name']}' added to seat {d['seat']}."
            )

    def _edit_student(self):
        sid = self._selected_id()
        if not sid:
            return
        student = self.db.get_student_by_id(sid)
        fee = self.db.get_fee_record(sid)
        dlg = StudentDialog(self, self.db, student=student, fee=fee)
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            ok, msg = self.db.update_student(
                sid,
                d["name"],
                d["mobile"],
                d["admission"],
                d["monthly_fee"],
                d.get("shift_type", "FULL_DAY"),
            )
            if not ok:
                messagebox.showerror("Could Not Update Student", msg)
                return

            try:
                self._apply_photo_result(sid, d)
            except Exception as exc:
                messagebox.showwarning(
                    "Photo Not Saved",
                    f"Student details were updated, but the photo change failed:\n{exc}",
                )

            self.refresh()
            self._update_info_panel(sid)
            messagebox.showinfo("Updated", "Student record updated.")

    def _mark_old(self):
        sid = self._selected_id()
        if not sid:
            return
        student = self.db.get_student_by_id(sid)
        if student["status"] == "Old Student":
            messagebox.showinfo(
                "Info", "This student is already marked as Old Student."
            )
            return
        if not messagebox.askyesno(
            "Confirm",
            f"Mark '{student['full_name']}' as Old Student?\nTheir seat will be freed.",
        ):
            return
        dlg = OldStudentDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.db.mark_old_student(sid, dlg.result["exit_date"])
            self.refresh()
            messagebox.showinfo("Done", "Student marked as Old Student. Seat freed.")

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="students.csv",
        )
        if path:
            self.db.export_students_csv(path)
            messagebox.showinfo("Exported", f"Students exported to:\n{path}")
