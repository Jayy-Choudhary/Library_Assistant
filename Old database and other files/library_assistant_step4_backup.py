"""
Library Assistant - A modern desktop application for library seat and fee management.
Built with CustomTkinter and SQLite.
"""

import customtkinter as ctk
from datetime import date
from tkinter import messagebox, filedialog
import tkinter as tk
from dialogs import (
    StudentDialog,
    OldStudentDialog,
    PaymentDialog,
    FeeUpdateDialog,
    AddSeatsDialog,
)

from config.theme import COLORS, FONT_TITLE, FONT_HEADER, FONT_BODY, FONT_SMALL, FONT_CARD_NUM, FONT_CARD_LBL

from database.database import Database



# ─────────────────────────────────────────────
#  REUSABLE UI COMPONENTS

# ─────────────────────────────────────────────
from widgets.components import styled_treeview, card, label_entry, action_button


# ─────────────────────────────────────────────
#  PAGE CLASSES
# ─────────────────────────────────────────────
class PageBase(tk.Frame):
    def __init__(self, parent, db: Database):
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
        tk.Label(f, text=text, font=FONT_TITLE,
                 bg=COLORS["bg"], fg=COLORS["text_primary"]).pack(side="left")
        f.pack(fill="x", padx=28, pady=(22, 6))
        return f

    def _divider(self, parent=None):
        p = parent or self
        tk.Frame(p, bg=COLORS["border"], height=1).pack(fill="x", padx=28, pady=4)



# ─────── DASHBOARD PAGE ───────────────────────
class DashboardPage(PageBase):
    def _build(self):
        self._section_header("📊  Dashboard")
        self._divider()

        # Stat cards row
        self.cards_frame = tk.Frame(self, bg=COLORS["bg"])
        self.cards_frame.pack(fill="x", padx=20, pady=10)
        for i in range(6):
            self.cards_frame.columnconfigure(i, weight=1)

        # Due students table
        tk.Label(self, text="Fee Due Students",
                 font=FONT_HEADER, bg=COLORS["bg"], fg=COLORS["danger"]).pack(
            anchor="w", padx=28, pady=(14, 4))

        tframe, self.due_tree = styled_treeview(
            self, ["Seat No.", "Student Name", "Due Amount (₹)"],
            {"Seat No.": 110, "Student Name": 240, "Due Amount (₹)": 160},
            height=10
        )
        tframe.pack(fill="both", expand=True, padx=28, pady=(0, 20))

        self.refresh()

    def refresh(self):
        # Clear old cards
        for w in self.cards_frame.winfo_children():
            w.destroy()

        total, occ, avail = self.db.seat_counts()
        active, old       = self.db.count_students()
        due_rows          = self.db.get_due_students()

        card_data = [
            ("Total Seats",      total,          COLORS["accent"]),
            ("Occupied",         occ,            COLORS["accent2"]),
            ("Available",        avail,          COLORS["success"]),
            ("Active Students",  active,         "#0EA5E9"),
            ("Old Students",     old,            COLORS["text_secondary"]),
            ("Fee Due Students", len(due_rows),  COLORS["danger"]),
        ]
        for col, (title, val, color) in enumerate(card_data):
            card(self.cards_frame, title, val, color, col=col, row=0)

        # Due tree
        for item in self.due_tree.get_children():
            self.due_tree.delete(item)
        for r in due_rows:
            self.due_tree.insert("", "end",
                values=(r["seat_number"], r["full_name"], f"₹{r['due_amount']:.0f}"))


# ─────── STUDENTS PAGE ────────────────────────
class StudentsPage(PageBase):
    def _build(self):
        self._section_header("🎓  Students")
        self._divider()

        # Toolbar
        tb = tk.Frame(self, bg=COLORS["bg"])
        tb.pack(fill="x", padx=28, pady=8)

        action_button(tb, "+ Add Student",  self._add_student).pack(side="left", padx=4)
        action_button(tb, "✏  Edit",        self._edit_student,  color="#0EA5E9").pack(side="left", padx=4)
        action_button(tb, "🔴 Mark Old",    self._mark_old,      color=COLORS["warning"]).pack(side="left", padx=4)
        action_button(tb, "📤 Export CSV",  self._export_csv,    color=COLORS["success"]).pack(side="left", padx=4)

        # Search
        tk.Label(tb, text="Search:", font=FONT_BODY,
                 bg=COLORS["bg"], fg=COLORS["text_secondary"]).pack(side="left", padx=(20, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._search())
        tk.Entry(tb, textvariable=self.search_var, font=FONT_BODY, width=22,
                 bg="#F9FAFB", relief="flat", bd=6).pack(side="left", padx=4)

        # Filter
        self.filter_var = tk.StringVar(value="All")
        for val in ("All", "Active", "Old Student"):
            tk.Radiobutton(tb, text=val, variable=self.filter_var,
                           value=val, font=FONT_SMALL,
                           bg=COLORS["bg"], fg=COLORS["text_primary"],
                           activebackground=COLORS["bg"],
                           command=self.refresh).pack(side="left", padx=4)

        # Table
        cols = ["Seat No.", "Full Name", "Mobile Number", "Admission Date", "Exit Date", "Status"]
        widths = {"Seat No.": 100, "Full Name": 200, "Mobile Number": 140,
                  "Admission Date": 140, "Exit Date": 120, "Status": 110}
        tframe, self.tree = styled_treeview(self, cols, widths, height=18)
        tframe.pack(fill="both", expand=True, padx=28, pady=(4, 20))

        self.refresh()

    def _populate(self, rows):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in rows:
            tag = "old" if r["status"] == "Old Student" else ""
            self.tree.insert("", "end", iid=str(r["id"]),
                values=(r["seat_number"], r["full_name"], r["mobile_number"],
                        r["admission_date"], r["exit_date"] or "—", r["status"]),
                tags=(tag,))
        self.tree.tag_configure("old", foreground=COLORS["text_secondary"])

    def refresh(self):
        f = self.filter_var.get()
        if f == "All": rows = self.db.get_all_students()
        else:          rows = self.db.get_all_students(f)
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
            self.db.add_student(d["seat"], d["name"], d["mobile"],
                                d["admission"], d["monthly_fee"])
            self.refresh()
            messagebox.showinfo("Success", f"Student '{d['name']}' added to seat {d['seat']}.")

    def _edit_student(self):
        sid = self._selected_id()
        if not sid: return
        student = self.db.get_student_by_id(sid)
        fee     = self.db.get_fee_record(sid)
        dlg = StudentDialog(self, self.db, student=student, fee=fee)
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            self.db.update_student(sid, d["name"], d["mobile"], d["admission"], d["monthly_fee"])
            self.refresh()
            messagebox.showinfo("Updated", "Student record updated.")

    def _mark_old(self):
        sid = self._selected_id()
        if not sid: return
        student = self.db.get_student_by_id(sid)
        if student["status"] == "Old Student":
            messagebox.showinfo("Info", "This student is already marked as Old Student."); return
        if not messagebox.askyesno("Confirm",
                f"Mark '{student['full_name']}' as Old Student?\nTheir seat will be freed."):
            return
        dlg = OldStudentDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.db.mark_old_student(sid, dlg.result["exit_date"])
            self.refresh()
            messagebox.showinfo("Done", "Student marked as Old Student. Seat freed.")

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="students.csv")
        if path:
            self.db.export_students_csv(path)
            messagebox.showinfo("Exported", f"Students exported to:\n{path}")


# ─────── SEATS PAGE ───────────────────────────
class SeatsPage(PageBase):
    def _build(self):
        self._section_header("💺  Seat Management")
        self._divider()

        tb = tk.Frame(self, bg=COLORS["bg"])
        tb.pack(fill="x", padx=28, pady=8)

        action_button(tb, "+ Add Seats",   self._add_seats).pack(side="left", padx=4)

        self.filter_var = tk.StringVar(value="All")
        for val in ("All", "Available", "Occupied"):
            tk.Radiobutton(tb, text=val, variable=self.filter_var,
                           value=val, font=FONT_SMALL,
                           bg=COLORS["bg"], fg=COLORS["text_primary"],
                           activebackground=COLORS["bg"],
                           command=self.refresh).pack(side="left", padx=6)

        tframe, self.tree = styled_treeview(
            self, ["Seat Number", "Status"],
            {"Seat Number": 200, "Status": 200}, height=22
        )
        tframe.pack(fill="both", expand=True, padx=28, pady=(4, 20))
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = self.db.get_all_seats()
        f = self.filter_var.get()
        for r in rows:
            if f != "All" and r["status"] != f:
                continue
            tag = "occ" if r["status"] == "Occupied" else "avail"
            self.tree.insert("", "end", values=(r["seat_number"], r["status"]), tags=(tag,))
        self.tree.tag_configure("occ",   foreground=COLORS["danger"])
        self.tree.tag_configure("avail", foreground=COLORS["success"])

    def _add_seats(self):
        dlg = AddSeatsDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            added, skipped = self.db.add_seats_bulk(d["prefix"], d["start"], d["end"])
            self.refresh()
            messagebox.showinfo("Done", f"Added: {added}  |  Skipped (duplicates): {skipped}")


# ─────── FEES PAGE ────────────────────────────
class FeesPage(PageBase):
    def _build(self):
        self._section_header("💰  Fee Management")
        self._divider()

        tb = tk.Frame(self, bg=COLORS["bg"])
        tb.pack(fill="x", padx=28, pady=8)

        action_button(tb, "💳 Record Payment",  self._record_payment).pack(side="left", padx=4)
        action_button(tb, "✏ Update Fee",       self._update_fee,  color="#0EA5E9").pack(side="left", padx=4)
        action_button(tb, "📜 Payment History", self._show_history, color=COLORS["accent2"]).pack(side="left", padx=4)
        action_button(tb, "📤 Export CSV",       self._export_csv,  color=COLORS["success"]).pack(side="left", padx=4)

        self.filter_var = tk.StringVar(value="All")
        for val in ("All", "Due Only"):
            tk.Radiobutton(tb, text=val, variable=self.filter_var,
                           value=val, font=FONT_SMALL,
                           bg=COLORS["bg"], fg=COLORS["text_primary"],
                           activebackground=COLORS["bg"],
                           command=self.refresh).pack(side="left", padx=6)

        cols   = ["Seat No.", "Student Name", "Monthly Fee (₹)", "Due Date", "Due Amount (₹)", "Last Payment"]
        widths = {"Seat No.": 100, "Student Name": 200, "Monthly Fee (₹)": 140,
                  "Due Date": 120, "Due Amount (₹)": 140, "Last Payment": 140}
        tframe, self.tree = styled_treeview(self, cols, widths, height=18)
        tframe.pack(fill="both", expand=True, padx=28, pady=(4, 20))
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = self.db.get_fees_with_students()
        show_due = self.filter_var.get() == "Due Only"
        for r in rows:
            if show_due and r["due_amount"] <= 0:
                continue
            tag = "due" if r["due_amount"] > 0 else ""
            self.tree.insert("", "end", iid=str(r["student_id"]),
                values=(r["seat_number"], r["full_name"],
                        f"₹{r['monthly_fee']:.0f}", r["due_date"] or "—",
                        f"₹{r['due_amount']:.0f}", r["last_payment_date"] or "—"),
                tags=(tag,))
        self.tree.tag_configure("due", foreground=COLORS["danger"])

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a student first.")
            return None
        return int(sel[0])

    def _record_payment(self):
        sid = self._selected_id()
        if not sid: return
        student = self.db.get_student_by_id(sid)
        fee     = self.db.get_fee_record(sid)
        dlg = PaymentDialog(self, student["full_name"], fee["due_amount"])
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            ok, msg = self.db.record_payment(sid, d["amount"], d["date"], d["notes"])
            self.refresh()
            messagebox.showinfo("Payment Recorded", msg)

    def _update_fee(self):
        sid = self._selected_id()
        if not sid: return
        student = self.db.get_student_by_id(sid)
        fee     = self.db.get_fee_record(sid)
        dlg = FeeUpdateDialog(self, student["full_name"], fee["monthly_fee"], fee["due_amount"])
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            self.db.update_monthly_fee(sid, d["monthly_fee"], d["due_amount"])
            self.refresh()
            messagebox.showinfo("Updated", "Fee record updated.")

    def _show_history(self):
        sid = self._selected_id()
        if not sid: return
        student = self.db.get_student_by_id(sid)
        rows    = self.db.get_payment_history(sid)

        win = tk.Toplevel(self)
        win.title(f"Payment History — {student['full_name']} (Seat {student['seat_number']})")
        win.geometry("600x400")
        win.configure(bg=COLORS["card_bg"])

        tk.Label(win, text=f"Payment History — {student['full_name']}",
                 font=FONT_HEADER, bg=COLORS["accent"], fg="#FFFFFF",
                 padx=16, pady=10).pack(fill="x")

        tframe, tree = styled_treeview(
            win, ["#", "Amount (₹)", "Payment Date", "Notes"],
            {"#": 50, "Amount (₹)": 130, "Payment Date": 160, "Notes": 240},
            height=12
        )
        tframe.pack(fill="both", expand=True, padx=16, pady=16)

        for i, r in enumerate(rows, 1):
            tree.insert("", "end", values=(i, f"₹{r['amount']:.0f}", r["payment_date"], r["notes"] or "—"))

        if not rows:
            tree.insert("", "end", values=("—", "—", "No payments recorded", "—"))

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="fees.csv")
        if path:
            self.db.export_fees_csv(path)
            messagebox.showinfo("Exported", f"Fee records exported to:\n{path}")


# ─────────────────────────────────────────────
#  MAIN APPLICATION WINDOW
# ─────────────────────────────────────────────
class LibraryAssistant(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Library Assistant")
        self.geometry("1200x720")
        self.minsize(900, 600)
        self.configure(bg=COLORS["sidebar"])

        self.db = Database()
        self._current_page = None
        self._nav_buttons  = {}

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
        tk.Label(logo_frame, text="📚", font=("Helvetica", 28),
                 bg=COLORS["sidebar"], fg="#FFFFFF").pack()
        tk.Label(logo_frame, text="Library\nAssistant",
                 font=("Georgia", 15, "bold"),
                 bg=COLORS["sidebar"], fg="#FFFFFF",
                 justify="center").pack()
        tk.Frame(self.sidebar, bg=COLORS["sidebar_active_bg"], height=1).pack(fill="x", pady=8)

        # Nav items
        nav_items = [
            ("dashboard", "🏠  Dashboard"),
            ("students",  "🎓  Students"),
            ("seats",     "💺  Seats"),
            ("fees",      "💰  Fees"),
        ]
        for key, label in nav_items:
            btn = tk.Button(
                self.sidebar, text=label,
                font=FONT_BODY, fg=COLORS["sidebar_text"],
                bg=COLORS["sidebar"], relief="flat", bd=0,
                anchor="w", padx=28, pady=12,
                activebackground=COLORS["sidebar_active_bg"],
                activeforeground="#FFFFFF",
                cursor="hand2",
                command=lambda k=key: self._show_page(k)
            )
            btn.pack(fill="x")
            self._nav_buttons[key] = btn

        # Footer
        tk.Frame(self.sidebar, bg=COLORS["sidebar_active_bg"], height=1).pack(fill="x", side="bottom", pady=8)
        tk.Label(self.sidebar, text="v1.0  •  SQLite", font=FONT_SMALL,
                 bg=COLORS["sidebar"], fg=COLORS["sidebar_text"]).pack(side="bottom", pady=6)

        # ── Main content area ─────────────────────
        self.content = tk.Frame(self, bg=COLORS["bg"])
        self.content.pack(side="left", fill="both", expand=True)

        self._pages = {
            "dashboard": DashboardPage(self.content, self.db),
            "students":  StudentsPage(self.content,  self.db),
            "seats":     SeatsPage(self.content,     self.db),
            "fees":      FeesPage(self.content,      self.db),
        }

    def _show_page(self, key):
        # Update sidebar button styles
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(bg=COLORS["sidebar_active_bg"],
                               fg=COLORS["sidebar_active_text"])
            else:
                btn.configure(bg=COLORS["sidebar"],
                               fg=COLORS["sidebar_text"])

        # Hide current, show new
        if self._current_page:
            self._pages[self._current_page].pack_forget()
        self._pages[key].pack(fill="both", expand=True)
        self._pages[key].refresh()
        self._current_page = key

    def _schedule_refresh(self):
        if self._current_page == "dashboard":
            self._pages["dashboard"].refresh()
        self.after(60_000, self._schedule_refresh)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = LibraryAssistant()
    app.mainloop()
