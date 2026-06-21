import tkinter as tk
from tkinter import messagebox, filedialog

from config.theme import COLORS, FONT_HEADER, FONT_SMALL
from dialogs import PaymentDialog, FeeUpdateDialog
from pages.fee_notices_dialog import FeeNoticesDialog
from widgets.components import styled_treeview, action_button


from .page_base import PageBase


class FeesPage(PageBase):
    def _build(self):
        self._section_header("💰  Fee Management")
        self._divider()

        tb = tk.Frame(self, bg=COLORS["bg"])
        tb.pack(fill="x", padx=28, pady=8)

        action_button(tb, "💳 Record Payment", self._record_payment).pack(
            side="left", padx=4
        )
        self.notice_btn = action_button(tb, "📢 Fee Notices", self._open_fee_notices)
        self.notice_btn.pack(side="left", padx=4)

        self._update_notice_button()

        action_button(tb, "✏ Update Fee", self._update_fee, color="#0EA5E9").pack(
            side="left", padx=4
        )
        action_button(
            tb, "📜 Payment History", self._show_history, color=COLORS["accent2"]
        ).pack(side="left", padx=4)
        action_button(
            tb, "📤 Export CSV", self._export_csv, color=COLORS["success"]
        ).pack(side="left", padx=4)

        self.filter_var = tk.StringVar(value="All")
        for val in ("All", "Due Only"):
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
            ).pack(side="left", padx=6)

        cols = [
            "Seat No.",
            "Student Name",
            "Monthly Fee (₹)",
            "Due Amount (₹)",
            "Next Due Date",
            "Notice Date",
            "Status",
            "Last Payment",
        ]
        widths = {
            "Seat No.": 100,
            "Student Name": 200,
            "Monthly Fee (₹)": 140,
            "Due Amount (₹)": 130,
            "Next Due Date": 120,
            "Notice Date": 120,
            "Status": 120,
            "Last Payment": 140,
        }

        tframe, self.tree = styled_treeview(self, cols, widths, height=18)
        tframe.pack(fill="both", expand=True, padx=28, pady=(4, 20))
        self.refresh()

    def _update_notice_button(self):
        count = self.db.get_pending_notice_count()
        # Ensure button exists (called safely during refresh lifecycle)
        if hasattr(self, "notice_btn") and self.notice_btn is not None:
            self.notice_btn.config(text=f"📢 Fee Notices ({count})")

    def refresh(self):
        self.db.generate_fee_notices()

        for item in self.tree.get_children():

            self.tree.delete(item)
        rows = self.db.get_fees_with_students()
        show_due = self.filter_var.get() == "Due Only"
        for r in rows:
            student_id = int(r["student_id"])
            status = self.db.get_fee_status(student_id)

            # Due Only filter means: include Reminder Due or Due.
            if show_due and status not in ("Reminder Due", "Due", "Overdue"):
                continue

            # Color tagging.
            tag = ""
            if status == "Paid":
                tag = "paid"
            elif status == "Reminder Due":
                tag = "reminder"
            elif status == "Due":
                tag = "due"
            elif status == "Overdue":
                tag = "overdue"
            elif status == "Cancelled":
                tag = "cancelled"

            # Map next/notice from fees subscription fields.
            # rows come from db.get_fees_with_students() which may not include these fields on legacy DBs.
            try:
                next_due = r["next_due_date"]
            except Exception:
                next_due = None
            try:
                notice_dt = r["notice_date"]
            except Exception:
                notice_dt = None

            self.tree.insert(
                "",
                "end",
                iid=str(student_id),
                values=(
                    r["seat_number"],
                    r["full_name"],
                    f"₹{r['monthly_fee']:.0f}",
                    f"₹{r['due_amount']:.0f}",
                    next_due or "—",
                    notice_dt or "—",
                    status,
                    r["last_payment_date"] or "—",
                ),
                tags=(tag,) if tag else (),
            )

        self.tree.tag_configure("paid", foreground=COLORS["success"])
        self.tree.tag_configure("reminder", foreground="#FACC15")
        self.tree.tag_configure("due", foreground="#FB923C")
        self.tree.tag_configure("overdue", foreground=COLORS["danger"])
        self.tree.tag_configure("cancelled", foreground="#6B7280")
        self._update_notice_button()

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a student first.")
            return None
        return int(sel[0])

    def _open_fee_notices(self):
        dlg = FeeNoticesDialog(self, self.db)
        self.wait_window(dlg)
        self.refresh()
        self._update_notice_button()

    def _record_payment(self):
        sid = self._selected_id()

        if not sid:
            return
        student = self.db.get_student_by_id(sid)
        fee = self.db.get_fee_record(sid)
        dlg = PaymentDialog(self, student["full_name"], fee["due_amount"])
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            ok, msg = self.db.record_payment(sid, d["amount"], d["date"], d["notes"])
            self.refresh()
            if ok:
                messagebox.showinfo("Payment Recorded", msg)
            else:
                messagebox.showerror("Payment Failed", msg)

    def _update_fee(self):
        sid = self._selected_id()
        if not sid:
            return
        student = self.db.get_student_by_id(sid)
        fee = self.db.get_fee_record(sid)
        dlg = FeeUpdateDialog(
            self, student["full_name"], fee["monthly_fee"], fee["due_amount"]
        )
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            self.db.update_monthly_fee(sid, d["monthly_fee"], d["due_amount"])
            self.refresh()
            messagebox.showinfo("Updated", "Fee record updated.")

    def _show_history(self):
        sid = self._selected_id()
        if not sid:
            return
        student = self.db.get_student_by_id(sid)
        rows = self.db.get_payment_history(sid)

        win = tk.Toplevel(self)
        win.title(
            f"Payment History — {student['full_name']} (Seat {student['seat_number']})"
        )
        win.geometry("600x400")
        win.configure(bg=COLORS["card_bg"])

        tk.Label(
            win,
            text=f"Payment History — {student['full_name']}",
            font=FONT_HEADER,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            padx=16,
            pady=10,
        ).pack(fill="x")

        tframe, tree = styled_treeview(
            win,
            ["#", "Amount (₹)", "Payment Date", "Notes"],
            {"#": 50, "Amount (₹)": 130, "Payment Date": 160, "Notes": 240},
            height=12,
        )
        tframe.pack(fill="both", expand=True, padx=16, pady=16)

        for i, r in enumerate(rows, 1):
            tree.insert(
                "",
                "end",
                values=(i, f"₹{r['amount']:.0f}", r["payment_date"], r["notes"] or "—"),
            )

        if not rows:
            tree.insert(
                "",
                "end",
                values=("—", "—", "No payments recorded", "—"),
            )

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="fees.csv",
        )
        if path:
            self.db.export_fees_csv(path)
            messagebox.showinfo("Exported", f"Fee records exported to:\n{path}")
