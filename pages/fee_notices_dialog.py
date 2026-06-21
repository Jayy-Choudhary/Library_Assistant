import tkinter as tk
from tkinter import messagebox
from urllib.parse import quote
import webbrowser

from config.theme import COLORS, FONT_HEADER, FONT_BODY, FONT_SMALL
from widgets.components import styled_treeview, action_button


class FeeNoticesDialog(tk.Toplevel):
    """Operational notice center for fee renewal notices."""

    FILTERS = (
        "All",
        "Pending",
        "Paid",
        "Cancelled",
        "Reminder Due",
        "Due",
        "Overdue",
    )

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.notice_rows = {}
        self.selected_notice_id = None

        self.title("Fee Notice Center")
        self.geometry("1080x680")
        self.minsize(980, 620)
        self.configure(bg=COLORS["card_bg"])

        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - 1080) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - 680) // 2)
        self.geometry(f"+{x}+{y}")

        header = tk.Frame(self, bg=COLORS["card_bg"], padx=16, pady=12)
        header.pack(fill="x")

        tk.Label(
            header,
            text="Fee Notice Center",
            font=FONT_HEADER,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            padx=12,
            pady=8,
        ).pack(anchor="w")

        self._build_toolbar()
        self._build_table()
        self._build_details()
        self._build_footer()

        self.refresh(generate=True)

    def _build_toolbar(self):
        tb = tk.Frame(self, bg=COLORS["card_bg"], padx=16, pady=8)
        tb.pack(fill="x")

        tk.Label(
            tb,
            text="Filter:",
            font=FONT_SMALL,
            bg=COLORS["card_bg"],
            fg=COLORS["text_secondary"],
        ).pack(side="left", padx=(0, 8))

        self.filter_var = tk.StringVar(value="Pending")
        for val in self.FILTERS:
            tk.Radiobutton(
                tb,
                text=val,
                variable=self.filter_var,
                value=val,
                font=FONT_SMALL,
                bg=COLORS["card_bg"],
                fg=COLORS["text_primary"],
                activebackground=COLORS["card_bg"],
                command=self.refresh,
            ).pack(side="left", padx=5)

        action_button(
            tb,
            "Refresh / Generate Notices",
            lambda: self.refresh(generate=True),
            color=COLORS["accent2"],
        ).pack(side="right", padx=4)

    def _build_table(self):
        cols = [
            "Student Name",
            "Seat Number",
            "Mobile Number",
            "Notice Date",
            "Due Date",
            "Due Amount",
            "Status",
        ]
        widths = {
            "Student Name": 220,
            "Seat Number": 100,
            "Mobile Number": 130,
            "Notice Date": 120,
            "Due Date": 120,
            "Due Amount": 110,
            "Status": 140,
        }
        tframe, self.tree = styled_treeview(self, cols, widths, height=12)
        tframe.pack(fill="both", expand=True, padx=16, pady=(4, 10))

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.tag_configure("pending", foreground=COLORS["warning"])
        self.tree.tag_configure("paid", foreground=COLORS["success"])
        self.tree.tag_configure("cancelled", foreground=COLORS["text_secondary"])
        self.tree.tag_configure("reminder", foreground="#CA8A04")
        self.tree.tag_configure("due", foreground="#EA580C")
        self.tree.tag_configure("overdue", foreground=COLORS["danger"])

    def _build_details(self):
        details = tk.Frame(self, bg=COLORS["card_bg"], padx=16, pady=6)
        details.pack(fill="x")

        details_header = tk.Frame(details, bg=COLORS["card_bg"])
        details_header.pack(fill="x", pady=(0, 4))

        tk.Label(
            details_header,
            text="Notice Message",
            font=FONT_HEADER,
            bg=COLORS["card_bg"],
            fg=COLORS["text_primary"],
        ).pack(side="left", anchor="w")

        tk.Button(
            details_header,
            text="📄↩",
            command=self._copy_notice_message,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            font=FONT_SMALL,
            relief="flat",
            bd=0,
            padx=8,
            pady=3,
            activebackground=COLORS["accent"],
            cursor="hand2",
        ).pack(side="left", padx=(8, 0))

        self.message_text = tk.Text(
            details,
            height=5,
            wrap="word",
            font=FONT_BODY,
            bg="#F9FAFB",
            fg=COLORS["text_primary"],
            relief="flat",
            bd=8,
        )
        self.message_text.pack(fill="x")
        self.message_text.configure(state="disabled")

    def _build_footer(self):
        footer = tk.Frame(self, bg=COLORS["card_bg"], padx=16, pady=12)
        footer.pack(fill="x")

        action_button(
            footer,
            "Copy Notice Message",
            self._copy_notice_message,
            color=COLORS["accent"],
        ).pack(side="left", padx=4)
        action_button(
            footer,
            "Copy WhatsApp Text",
            self._copy_whatsapp_text,
            color=COLORS["success"],
        ).pack(side="left", padx=4)
        action_button(
            footer,
            "Open WhatsApp",
            self._open_whatsapp,
            color=COLORS["success"],
        ).pack(side="left", padx=4)
        action_button(
            footer,
            "📢 Send All Pending",
            self._send_all_pending,
            color="#0f766e",
        ).pack(side="left", padx=4)
        action_button(
            footer,
            "Mark Cancelled",
            self._mark_cancelled,
            color=COLORS["danger"],
        ).pack(side="left", padx=4)
        action_button(
            footer,
            "Close",
            self.destroy,
            color=COLORS.get("accent2", COLORS["accent"]),
        ).pack(side="right", padx=4)

    def refresh(self, generate=False):
        if generate:
            self.db.generate_fee_notices()

        selected_id = self.selected_notice_id
        self.notice_rows = {}
        self.selected_notice_id = None

        for item in self.tree.get_children():
            self.tree.delete(item)

        rows = self.db.get_notice_center_rows(self.filter_var.get())
        for row in rows:
            notice_id = int(row["id"])
            display_status = self._display_status(row)
            due_amount = float(row["due_amount"] or 0)
            tag = self._tag_for(row, display_status)
            self.notice_rows[notice_id] = row

            self.tree.insert(
                "",
                "end",
                iid=str(notice_id),
                values=(
                    row["full_name"] or "-",
                    row["seat_number"] or "-",
                    row["mobile_number"] or "-",
                    row["notice_date"] or "-",
                    row["due_date"] or "-",
                    f"Rs. {due_amount:.0f}",
                    display_status,
                ),
                tags=(tag,) if tag else (),
            )

        if selected_id and str(selected_id) in self.tree.get_children():
            self.tree.selection_set(str(selected_id))
            self.tree.focus(str(selected_id))
            self._show_message_for(selected_id)
        else:
            self._clear_message()

    def _display_status(self, row):
        notice_status = row["status"] or "Pending"
        if notice_status in ("Paid", "Cancelled"):
            return notice_status

        fee_status = self.db.get_fee_status(int(row["student_id"]))
        if fee_status in ("Reminder Due", "Due", "Overdue"):
            return fee_status
        return notice_status

    def _tag_for(self, row, display_status):
        notice_status = row["status"] or "Pending"
        if notice_status == "Paid":
            return "paid"
        if notice_status == "Cancelled":
            return "cancelled"
        if display_status == "Reminder Due":
            return "reminder"
        if display_status == "Due":
            return "due"
        if display_status == "Overdue":
            return "overdue"
        return "pending"

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            self.selected_notice_id = None
            self._clear_message()
            return

        notice_id = int(sel[0])
        self.selected_notice_id = notice_id
        self._show_message_for(notice_id)

    def _show_message_for(self, notice_id):
        row = self.notice_rows.get(notice_id)
        message = row["message"] if row else ""

        self.message_text.configure(state="normal")
        self.message_text.delete("1.0", "end")
        self.message_text.insert("1.0", message or "")
        self.message_text.configure(state="disabled")

    def _clear_message(self):
        self.message_text.configure(state="normal")
        self.message_text.delete("1.0", "end")
        self.message_text.configure(state="disabled")

    def _selected_row(self):
        if self.selected_notice_id is None:
            messagebox.showwarning(
                "No Selection",
                "Select a notice first.",
                parent=self,
            )
            return None
        row = self.notice_rows.get(self.selected_notice_id)
        if row is None:
            messagebox.showwarning(
                "No Selection",
                "Selected notice is no longer available.",
                parent=self,
            )
        return row

    def _copy_to_clipboard(self, text, title):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        messagebox.showinfo(title, "Copied to clipboard.", parent=self)

    def _copy_notice_message(self):
        row = self._selected_row()
        if not row:
            return
        self._copy_to_clipboard(row["message"] or "", "Notice Message")

    def _copy_whatsapp_text(self):
        row = self._selected_row()
        if not row:
            return

        self._copy_to_clipboard(self._build_whatsapp_text(row), "WhatsApp Text")

    def _normalize_whatsapp_mobile(self, mobile_number):
        raw = str(mobile_number or "").strip()
        normalized = raw
        for ch in (" ", "-", "(", ")", "+"):
            normalized = normalized.replace(ch, "")

        if not normalized.isdigit():
            return None
        if len(normalized) == 10:
            return f"91{normalized}"
        if len(normalized) == 12 and normalized.startswith("91"):
            return normalized
        return None

    def _build_whatsapp_text(self, row):
        due_amount = float(row["due_amount"] or 0)
        return (
            f"Student: {row['full_name']}\n"
            f"Seat Number: {row['seat_number']}\n"
            f"Due Date: {row['due_date']}\n"
            f"Due Amount: Rs. {due_amount:.0f}\n\n"
            f"{row['message'] or ''}"
        )

    def _build_whatsapp_url(self, row):
        mobile_number = self._normalize_whatsapp_mobile(row["mobile_number"])
        if not mobile_number:
            return None
        message = quote(self._build_whatsapp_text(row))
        return f"https://wa.me/{mobile_number}?text={message}"

    def _open_whatsapp(self):
        row = self._selected_row()
        if not row:
            return

        url = self._build_whatsapp_url(row)
        if not url:
            messagebox.showerror(
                "Invalid Mobile Number",
                "WhatsApp requires a valid 10-digit Indian mobile number.",
                parent=self,
            )
            return

        webbrowser.open(url)

    def _mark_cancelled(self):
        row = self._selected_row()
        if not row:
            return
        if row["status"] != "Pending":
            messagebox.showinfo(
                "Cannot Cancel",
                "Only pending notices can be cancelled.",
                parent=self,
            )
            return

        ok = self.db.cancel_notice(int(row["id"]))
        if ok:
            self.refresh()
            messagebox.showinfo(
                "Notice Cancelled", "Notice marked as Cancelled.", parent=self
            )
        else:
            self.refresh()
            messagebox.showwarning(
                "Notice Not Changed",
                "The selected notice could not be cancelled.",
                parent=self,
            )

    def _send_all_pending(self):
        """Auto-send WhatsApp notices to all pending students via pywhatkit."""
        import threading
        import pywhatkit

        pending_rows = self.db.get_notice_center_rows("Pending")
        if not pending_rows:
            messagebox.showinfo(
                "No Pending Notices",
                "There are no pending notices to send.",
                parent=self,
            )
            return

        total = len(pending_rows)
        est_sec = total * 15
        est_min = round(est_sec / 60, 1)

        confirm = messagebox.askyesno(
            "Confirm Auto-Send",
            f"Automatically send WhatsApp notices to {total} student{'s' if total != 1 else ''}?\n\n"
            f"  • WhatsApp Web will open in your browser automatically\n"
            f"  • Messages are sent without any further clicks\n"
            f"  • Keep your browser window visible (don't minimize)\n"
            f"  • WhatsApp Web must be logged in\n\n"
            f"Estimated time: ~{est_sec}–{total*20} seconds (~{est_min} min)\n\n"
            "Start auto-send?",
            parent=self,
        )
        if not confirm:
            return

        # ── Build progress window ──────────────────────────────
        prog_win = tk.Toplevel(self)
        prog_win.title("Auto-Sending WhatsApp Notices…")
        prog_win.geometry("480x320")
        prog_win.configure(bg=COLORS["card_bg"])
        prog_win.resizable(False, False)
        prog_win.protocol("WM_DELETE_WINDOW", lambda: None)  # block close during send

        # Center it
        prog_win.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - 480) // 2
        py = self.winfo_rooty() + (self.winfo_height() - 320) // 2
        prog_win.geometry(f"+{max(px,0)}+{max(py,0)}")

        tk.Label(
            prog_win, text="🤖 Auto-Sending WhatsApp Notices",
            font=FONT_HEADER, bg=COLORS["accent"], fg="#FFFFFF",
            padx=12, pady=8,
        ).pack(fill="x")

        cur_label = tk.Label(
            prog_win, text="Starting…",
            font=FONT_BODY, bg=COLORS["card_bg"],
            fg=COLORS.get("text_primary", "#FFFFFF"),
            wraplength=440, anchor="w",
        )
        cur_label.pack(fill="x", padx=16, pady=(12, 2))

        # Progress bar (simulate with Scale)
        prog_var = tk.DoubleVar(value=0)
        prog_bar = tk.Scale(
            prog_win, from_=0, to=total, variable=prog_var,
            orient="horizontal", length=448, showvalue=False,
            state="disabled", bg=COLORS["card_bg"],
            troughcolor=COLORS.get("border", "#2d2d4e"),
            activebackground=COLORS["accent"],
        )
        prog_bar.pack(padx=16)

        pct_label = tk.Label(
            prog_win, text="0 / " + str(total),
            font=FONT_SMALL, bg=COLORS["card_bg"],
            fg=COLORS.get("text_secondary", "#888"),
        )
        pct_label.pack()

        # Scrollable log
        log_frame = tk.Frame(prog_win, bg=COLORS["card_bg"])
        log_frame.pack(fill="both", expand=True, padx=16, pady=(6, 12))
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")
        log_text = tk.Text(
            log_frame, height=7, width=58,
            font=FONT_SMALL,
            bg=COLORS.get("bg", "#12122a"),
            fg=COLORS.get("text_primary", "#e2e8f0"),
            relief="flat", bd=4,
            yscrollcommand=scrollbar.set,
            state="disabled",
        )
        log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=log_text.yview)

        def log(msg):
            log_text.configure(state="normal")
            log_text.insert("end", msg + "\n")
            log_text.see("end")
            log_text.configure(state="disabled")

        # ── Background thread ──────────────────────────────────
        def send_thread():
            import threading
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import pyperclip
            import time

            sent = 0
            failed = 0
            skipped = 0

            # ── Open persistent Chrome session ──────────────────
            prog_win.after(0, lambda: cur_label.config(text="Opening WhatsApp Web…"))
            try:
                import os
                here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                profile_dir = os.path.join(here, ".wa_chrome_profile")
                os.makedirs(profile_dir, exist_ok=True)

                opts = Options()
                opts.add_argument(f"--user-data-dir={profile_dir}")
                opts.add_argument("--no-first-run")
                opts.add_argument("--no-default-browser-check")
                opts.add_experimental_option("excludeSwitches", ["enable-automation"])
                opts.add_experimental_option("useAutomationExtension", False)

                driver = webdriver.Chrome(options=opts)
                driver.maximize_window()

                # Navigate to WA Web if not already there
                if "web.whatsapp.com" not in driver.current_url:
                    driver.get("https://web.whatsapp.com")
                    prog_win.after(0, lambda: log("🌐 Waiting for WhatsApp Web to load…"))
                    time.sleep(7)

                prog_win.after(0, lambda: log("✅ WhatsApp Web is ready"))
            except Exception as exc:
                prog_win.after(0, lambda e=str(exc)[:80]: log(f"❌ Could not open browser: {e}"))
                prog_win.after(0, lambda: (
                    cur_label.config(text="❌ Browser failed to open"),
                    prog_win.protocol("WM_DELETE_WINDOW", prog_win.destroy),
                ))
                return

            # ── Send to each student via search bar ─────────────
            wait = WebDriverWait(driver, 20)

            for i, row in enumerate(pending_rows, start=1):
                name   = row["full_name"] or "Unknown"
                mobile = self._normalize_whatsapp_mobile(row["mobile_number"])

                # Update UI (thread-safe via after)
                prog_win.after(0, lambda n=name, idx=i: (
                    cur_label.config(text=f"Sending {idx}/{total}: {n}…"),
                    prog_var.set(idx - 1),
                    pct_label.config(text=f"{idx} / {total}"),
                ))

                if not mobile:
                    skipped += 1
                    prog_win.after(0, lambda n=name: log(f"⚠  Skipped {n} — invalid mobile number"))
                    continue

                try:
                    # Helper to find element with fallbacks
                    def find_element_with_fallbacks(xpaths, name="element"):
                        # 1. Try combined union XPath first
                        union_parts = [x for x in xpaths if not x.startswith('(')]
                        if union_parts:
                            combined = ' | '.join(union_parts)
                            try:
                                return wait.until(EC.element_to_be_clickable((By.XPATH, combined)))
                            except Exception:
                                pass

                        # 2. Fallback to sequential search with short timeout to log specific errors
                        errors = []
                        short_wait = WebDriverWait(driver, 2)
                        for xpath in xpaths:
                            try:
                                return short_wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                            except Exception as e:
                                errors.append(f"{xpath}: {str(e)[:40]}")
                        raise Exception(f"Could not find {name}. Errors: {'; '.join(errors)}")

                    # 1. Click search box
                    search_box_xpaths = [
                        '//div[@data-testid="chat-list-search-container"]//input',
                        '//input[@placeholder="Search or start a new chat"]',
                        '//input[@aria-label="Search or start a new chat"]',
                        '//input[@role="textbox"]',
                        '//div[@aria-label="Search input textbox"]',
                        '//div[@contenteditable="true"][@data-tab="3"]',
                        '//div[@title="Search input textbox"]',
                        '//div[@data-testid="chat-list-search"]//div[@contenteditable="true"]',
                        '//div[@role="textbox"][@contenteditable="true"]'
                    ]
                    search_box = find_element_with_fallbacks(search_box_xpaths, "search box")
                    search_box.click()
                    time.sleep(0.3)
                    search_box.send_keys(Keys.CONTROL + "a")
                    search_box.send_keys(Keys.DELETE)
                    search_box.send_keys(Keys.ESCAPE)
                    time.sleep(0.3)

                    # 2. Type phone number and wait dynamically
                    # Re-find search_box in case it became stale after clearing
                    search_box = find_element_with_fallbacks(search_box_xpaths, "search box")
                    search_box.send_keys(f"+{mobile}")

                    result_xpath = '//div[@data-testid="cell-frame-container"]'
                    no_results_xpath = '//*[contains(., "No chats, contacts or messages found") or contains(., "No chats found") or contains(., "No contacts found") or contains(., "No results found") or contains(., "No matches found")]'

                    first_result = None
                    not_on_whatsapp = False

                    for _ in range(25):  # max 5 seconds (25 * 0.2s)
                        if driver.find_elements(By.XPATH, no_results_xpath):
                            not_on_whatsapp = True
                            break

                        res = driver.find_elements(By.XPATH, result_xpath)
                        if len(res) == 1:
                            if res[0].is_displayed():
                                first_result = res[0]
                                break
                        elif len(res) > 1:
                            last_four = mobile[-4:]
                            first_name = name.split()[0] if name else ""
                            for cell in res:
                                try:
                                    cell_text = cell.text or ""
                                    if last_four in cell_text or (first_name and first_name.lower() in cell_text.lower()):
                                        first_result = cell
                                        break
                                except Exception:
                                    pass
                            if first_result:
                                break
                        time.sleep(0.2)

                    if not_on_whatsapp:
                        raise Exception("NOT_ON_WHATSAPP")

                    if not first_result:
                        raise Exception("Could not find search result cell.")

                    # 3. Click search result
                    driver.execute_script("arguments[0].scrollIntoView(true);", first_result)
                    time.sleep(0.3)
                    try:
                        first_result.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", first_result)
                    time.sleep(1.2)

                    # 4. Find message input and paste
                    msg_input_xpaths = [
                        '//div[@aria-label="Type a message"][@contenteditable="true"]',
                        '//div[@data-tab="10"][@contenteditable="true"]',
                        '//div[@data-testid="conversation-compose-box-input"]',
                        '//footer//div[@contenteditable="true"]'
                    ]
                    msg_input = find_element_with_fallbacks(msg_input_xpaths, "message input box")
                    driver.execute_script("arguments[0].scrollIntoView(true);", msg_input)
                    time.sleep(0.3)
                    try:
                        msg_input.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", msg_input)
                    time.sleep(0.3)
                    message = self._build_whatsapp_text(row)
                    pyperclip.copy(message)
                    msg_input.send_keys(Keys.CONTROL + "v")
                    time.sleep(0.6)

                    # 5. Send
                    msg_input.send_keys(Keys.ENTER)
                    time.sleep(1.2)

                    sent += 1
                    prog_win.after(0, lambda n=name: log(f"✅ Sent to {n}"))
                except Exception as exc:
                    err_msg = str(exc)
                    if "NOT_ON_WHATSAPP" in err_msg:
                        skipped += 1
                        prog_win.after(0, lambda n=name: log(f"⚠  Skipped {n} — number is not on WhatsApp"))
                    else:
                        failed += 1
                        prog_win.after(0, lambda n=name, e=err_msg[:60]: log(f"❌ Failed for {n}: {e}"))

            # Finish
            prog_win.after(0, lambda: (
                prog_var.set(total),
                pct_label.config(text=f"{total} / {total}"),
                cur_label.config(text="✅ All done!"),
                prog_win.protocol("WM_DELETE_WINDOW", prog_win.destroy),
            ))

            summary = (
                f"Bulk Auto-Send Complete!\n\n"
                f"  Sent    : {sent}\n"
                f"  Skipped : {skipped} (invalid number)"
            )
            if failed:
                summary += f"\n  Failed  : {failed}"

            prog_win.after(200, lambda: messagebox.showinfo(
                "Bulk Send Summary", summary, parent=prog_win
            ))
            prog_win.after(500, prog_win.destroy)

        t = threading.Thread(target=send_thread, daemon=True)
        t.start()

