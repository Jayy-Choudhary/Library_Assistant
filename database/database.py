import sqlite3
import csv
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

from config.paths import DB_PATH, REMOTE_URL, API_KEY

GRACE_PERIOD_DAYS = 3


class Database:
    def __new__(cls, db_path=None):
        if REMOTE_URL:
            return RemoteDatabaseProxy(REMOTE_URL, API_KEY)
        instance = super().__new__(cls)
        return instance

    def __init__(self, db_path=None):
        self.db_path = str(db_path or DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # allow usage from FastAPI worker threads
        self.conn = sqlite3.connect(
            self.db_path,
            timeout=10,
            check_same_thread=False,
        )

        self.conn.row_factory = sqlite3.Row
        self._configure_connection()
        self._create_tables()
        self._ensure_seats_room_column()
        self._migrate_fees_subscription_columns()
        self._migrate_student_photo_path_column()
        self._migrate_fee_notices_sent_columns()

    def _configure_connection(self):
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 10000")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
        PRAGMA foreign_keys = ON;

        -- Create tables (idempotent).
        CREATE TABLE IF NOT EXISTS seats (
            seat_number TEXT PRIMARY KEY,
            status      TEXT NOT NULL DEFAULT 'Available'  -- Available | Occupied
        );


        CREATE TABLE IF NOT EXISTS students (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            seat_number    TEXT NOT NULL,
            full_name      TEXT NOT NULL,
            mobile_number  TEXT NOT NULL,
            admission_date TEXT NOT NULL,
            exit_date      TEXT,
            status         TEXT NOT NULL DEFAULT 'Active',  -- Active | Old Student
            shift_type     TEXT NOT NULL DEFAULT 'FULL_DAY',
            photo_path     TEXT, -- nullable; optional Student Photo on disk

            FOREIGN KEY (seat_number) REFERENCES seats(seat_number)
        );



        CREATE TABLE IF NOT EXISTS fees (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id        INTEGER NOT NULL,
            monthly_fee       REAL NOT NULL DEFAULT 0,
            due_date          TEXT,
            due_amount        REAL NOT NULL DEFAULT 0,
            last_payment_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS payment_history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id     INTEGER NOT NULL,
            amount         REAL NOT NULL,
            payment_date   TEXT NOT NULL,
            notes          TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS fee_notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            notice_date TEXT NOT NULL,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            sent_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, due_date)
        );

        CREATE TABLE IF NOT EXISTS room_layouts (
            room          TEXT PRIMARY KEY,
            rows          INTEGER NOT NULL,
            columns       INTEGER NOT NULL,
            seat_spacing  INTEGER NOT NULL DEFAULT 8
        );
        """)
        self.conn.commit()

    def _ensure_seats_room_column(self):
        """Ensure seats.room exists (conditional migration for legacy DBs).

        Required behavior:
        - If room column missing: add it with NOT NULL DEFAULT 'A'
        - Migrate existing data using seat_number prefix:
            A* -> A, B* -> B, C* -> C
        - If already present: do nothing.
        """
        cur = self.conn.cursor()
        cols = [
            row["name"] for row in cur.execute("PRAGMA table_info(seats)").fetchall()
        ]
        if "room" in cols:
            return False

        # Add column with default.
        cur.execute("ALTER TABLE seats ADD COLUMN room TEXT NOT NULL DEFAULT 'A'")

        # Backfill based on seat_number prefix.
        cur.execute("UPDATE seats SET room='A' WHERE seat_number LIKE 'A%'")
        cur.execute("UPDATE seats SET room='B' WHERE seat_number LIKE 'B%'")
        cur.execute("UPDATE seats SET room='C' WHERE seat_number LIKE 'C%'")

        self.conn.commit()
        return True

    def _migrate_student_photo_path_column(self):
        """Migration-safe column addition for optional Student Photo.

        Adds a nullable `photo_path` column to students if missing.
        Existing students will have NULL (no photo).
        """
        cur = self.conn.cursor()
        cols = [
            row["name"] for row in cur.execute("PRAGMA table_info(students)").fetchall()
        ]
        if "photo_path" in cols:
            return
        cur.execute("ALTER TABLE students ADD COLUMN photo_path TEXT")
        self.conn.commit()

    def _migrate_fee_notices_sent_columns(self):
        """Migration-safe column addition for tracking sent state of fee notices."""
        cur = self.conn.cursor()
        cols = [
            row["name"] for row in cur.execute("PRAGMA table_info(fee_notices)").fetchall()
        ]
        if "sent_at" in cols:
            return
        cur.execute("ALTER TABLE fee_notices ADD COLUMN sent_at TEXT")
        self.conn.commit()

    def _migrate_fees_subscription_columns(self):
        """Backfill migration-safe columns in fees for Stage 4.1 (subscription renewal).

        Idempotent:
        - Adds columns only if missing.
        - If last_notice_generated is NULL, initialize it.
        - Does NOT overwrite next_due_date/notice_date if already populated.
        """
        cur = self.conn.cursor()
        cols = [
            row["name"] for row in cur.execute("PRAGMA table_info(fees)").fetchall()
        ]

        # Add missing columns.
        to_add = []
        if "next_due_date" not in cols:
            to_add.append("ALTER TABLE fees ADD COLUMN next_due_date TEXT")
        if "notice_date" not in cols:
            to_add.append("ALTER TABLE fees ADD COLUMN notice_date TEXT")
        if "last_notice_generated" not in cols:
            to_add.append("ALTER TABLE fees ADD COLUMN last_notice_generated TEXT")

        for sql in to_add:
            cur.execute(sql)

        # Backfill for existing rows where columns are NULL.
        # due_date/next_due_date = admission_date + 1 month (calendar month)
        # notice_date = due_date - GRACE_PERIOD_DAYS days.
        # Do not overwrite populated legacy values.
        if "next_due_date" in [
            row["name"] for row in cur.execute("PRAGMA table_info(fees)").fetchall()
        ]:
            # Use SQLite date modifiers. We treat admission_date as YYYY-MM-DD.
            # SQLite: date(admission_date, '+1 month')
            cur.execute("""
                UPDATE fees
                SET next_due_date = (
                    CASE
                        WHEN (next_due_date IS NULL OR next_due_date='') AND EXISTS (
                            SELECT 1 FROM students s WHERE s.id = fees.student_id
                        ) THEN date((SELECT s.admission_date FROM students s WHERE s.id = fees.student_id), '+1 month')
                        ELSE next_due_date
                    END
                )
                """)

        cur.execute("""
            UPDATE fees
            SET due_date = next_due_date
            WHERE (due_date IS NULL OR due_date='')
              AND next_due_date IS NOT NULL
        """)

        if "notice_date" in [
            row["name"] for row in cur.execute("PRAGMA table_info(fees)").fetchall()
        ]:
            cur.execute(f"""
                UPDATE fees
                SET notice_date = (
                    CASE
                        WHEN notice_date IS NULL OR notice_date='' THEN date(next_due_date, '-{GRACE_PERIOD_DAYS} days')
                        ELSE notice_date
                    END
                )
                """)

        if "last_notice_generated" in [
            row["name"] for row in cur.execute("PRAGMA table_info(fees)").fetchall()
        ]:
            cur.execute("""
                UPDATE fees
                SET last_notice_generated = (
                    CASE
                        WHEN last_notice_generated IS NULL THEN notice_date
                        ELSE last_notice_generated
                    END
                )
                """)

        self.conn.commit()

    # ── Seats

    def get_all_seats(self):
        return self.conn.execute("SELECT * FROM seats ORDER BY seat_number").fetchall()

    def get_seats_by_room(self, room: str):
        room = (room or "A").strip().upper()
        if room not in ("A", "B", "C"):
            room = "A"
        return self.conn.execute(
            "SELECT * FROM seats WHERE COALESCE(room,'A')=? ORDER BY seat_number",
            (room,),
        ).fetchall()

    def assign_room_to_seat(self, seat_number: str, room: str):
        room = (room or "A").strip().upper()
        if room not in ("A", "B", "C"):
            room = "A"
        self.conn.execute(
            "UPDATE seats SET room=? WHERE seat_number=?",
            (room, seat_number),
        )
        self.conn.commit()

    def get_compatible_seats(self, target_shift_type: str):
        """Return seats compatible with target_shift_type based on existing validation rules.

        This is used for the Add/Edit Student seat dropdown to allow
        half-day sharing combinations while still blocking forbidden combos.
        """
        target_shift_type = (target_shift_type or "FULL_DAY").strip().upper()

        seat_rows = self.conn.execute(
            "SELECT seat_number FROM seats ORDER BY seat_number"
        ).fetchall()
        compatible = []
        for row in seat_rows:
            seat_number = row["seat_number"]
            ok, _err = self._is_valid_shift_combination(
                seat_number,
                target_shift_type,
                editing_student_id=None,
            )
            if ok:
                # Preserve backward semantics: seat must exist and either be Available
                # or be occupied by a compatible half-day.
                compatible.append(seat_number)
        return compatible

    def get_available_seats(self):
        # Backward-compat: used elsewhere; keep semantics unchanged.
        return self.conn.execute(
            "SELECT seat_number FROM seats WHERE status='Available' ORDER BY seat_number"
        ).fetchall()

    # ── Room Layouts ─────────────────────────────
    def get_room_layout(self, room: str):
        room = (room or "A").strip().upper()
        if room not in ("A", "B", "C"):
            room = "A"

        row = self.conn.execute(
            "SELECT rows, columns, seat_spacing FROM room_layouts WHERE room=?", (room,)
        ).fetchone()
        if not row:
            return 5, 5, 8

        return int(row["rows"]), int(row["columns"]), int(row["seat_spacing"])

    def set_room_layout(
        self, room: str, rows: int, columns: int, seat_spacing: int = 8
    ):
        room = (room or "A").strip().upper()
        if room not in ("A", "B", "C"):
            room = "A"

        self.conn.execute(
            """
            INSERT INTO room_layouts (room, rows, columns, seat_spacing)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(room) DO UPDATE SET
                rows=excluded.rows,
                columns=excluded.columns,
                seat_spacing=excluded.seat_spacing
            """,
            (room, int(rows), int(columns), int(seat_spacing)),
        )
        self.conn.commit()

    def add_seat(self, seat_number, room="A"):

        room = (room or "A").strip().upper()
        if room not in ("A", "B", "C"):
            room = "A"

        try:
            self.conn.execute(
                "INSERT INTO seats (seat_number, status, room) VALUES (?, 'Available', ?)",
                (seat_number, room),
            )
            self.conn.commit()
            return True, "Seat added."
        except sqlite3.IntegrityError:
            return False, f"Seat '{seat_number}' already exists."

    def add_seats_bulk(self, prefix, start, end, room="A"):
        added, skipped = 0, 0
        room = (room or "A").strip().upper()
        if room not in ("A", "B", "C"):
            room = "A"

        for i in range(start, end + 1):
            num = f"{prefix}{i:02d}"
            ok, _ = self.add_seat(num, room=room)
            if ok:
                added += 1
            else:
                skipped += 1
        return added, skipped

    def set_seat_status(self, seat_number, status):
        self.conn.execute(
            "UPDATE seats SET status=? WHERE seat_number=?", (status, seat_number)
        )
        self.conn.commit()

    def seat_counts(self):
        total = self.conn.execute("SELECT COUNT(*) FROM seats").fetchone()[0]
        occupied = self.conn.execute(
            "SELECT COUNT(*) FROM seats WHERE status='Occupied'"
        ).fetchone()[0]
        return total, occupied, total - occupied

    # ── Students ───────────────────────────────
    def _get_active_students_on_seat(self, seat_number):
        return self.conn.execute(
            "SELECT id, shift_type FROM students WHERE seat_number=? AND status='Active' ORDER BY id",
            (seat_number,),
        ).fetchall()

    def validate_seat_assignment(self, seat_number, shift_type, student_id=None):
        """Validate seat/shift assignment rules for FULL_DAY / HALF_DAY_DAY / HALF_DAY_NIGHT.

        If student_id is provided, its current shift record is ignored for validation
        (useful when editing an existing student).
        """
        return self._is_valid_shift_combination(
            seat_number,
            shift_type,
            editing_student_id=student_id,
        )

    def _is_valid_shift_combination(
        self, seat_number, new_shift_type, editing_student_id=None
    ):

        # Gather active shifts on the seat, excluding the editing student if provided.
        rows = self._get_active_students_on_seat(seat_number)
        shifts = []
        for r in rows:
            if editing_student_id is not None and int(r["id"]) == int(
                editing_student_id
            ):
                continue
            shifts.append(r["shift_type"])

        valid = {"FULL_DAY", "HALF_DAY_DAY", "HALF_DAY_NIGHT"}
        if new_shift_type not in valid:
            return False, f"Invalid shift type: {new_shift_type}."

        # Occupancy semantics:
        # Available if no active students on seat.
        # Occupied if at least one active student on seat.

        # Rules:
        # - FULL_DAY cannot share with any other active student on the same seat.
        # - HALF_DAY_DAY can share only with HALF_DAY_NIGHT (and only one of each).
        # - HALF_DAY_NIGHT can share only with HALF_DAY_DAY.
        # - Same half-day type cannot coexist with another half-day of same type.

        if not shifts:
            return True, None

        # If adding/updating to FULL_DAY: must have no other active students.
        if new_shift_type == "FULL_DAY":
            return False, "Full Day seat cannot be shared."

        # For half-day types, disallow FULL_DAY already present.
        if "FULL_DAY" in shifts:
            return False, "Half Day seat cannot share with a Full Day student."

        # Count occurrences of each shift among existing.
        counts = {"HALF_DAY_DAY": 0, "HALF_DAY_NIGHT": 0}
        for s in shifts:
            if s in counts:
                counts[s] += 1

        # Only allow at most one active half-day student per half slot.
        if new_shift_type == "HALF_DAY_DAY":
            if counts["HALF_DAY_DAY"] >= 1:
                return False, "Half Day (Day) cannot share with another Day student."
            if counts["HALF_DAY_NIGHT"] >= 1:
                # already has Night; allow because it matches combination but only one each
                # If adding Day when Night already exists and only one each, ok.
                pass
            return True, None

        if new_shift_type == "HALF_DAY_NIGHT":
            if counts["HALF_DAY_NIGHT"] >= 1:
                return (
                    False,
                    "Half Day (Night) cannot share with another Night student.",
                )
            return True, None

        return False, "Invalid shift combination."

    def _update_seat_status_from_active(self, seat_number):
        active_exists = (
            self.conn.execute(
                "SELECT 1 FROM students WHERE seat_number=? AND status='Active' LIMIT 1",
                (seat_number,),
            ).fetchone()
            is not None
        )
        self.set_seat_status(seat_number, "Occupied" if active_exists else "Available")

    def add_student(
        self,
        seat_number,
        full_name,
        mobile_number,
        admission_date,
        monthly_fee=0.0,
        shift_type="FULL_DAY",
    ):
        ok, err = self._is_valid_shift_combination(
            seat_number, shift_type, editing_student_id=None
        )
        if not ok:
            return False, err

        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO students (seat_number, full_name, mobile_number, admission_date, status, shift_type) "
            "VALUES (?, ?, ?, ?, 'Active', ?)",
            (seat_number, full_name, mobile_number, admission_date, shift_type),
        )
        student_id = cur.lastrowid

        # Ensure seat status reflects current active students on the seat.
        self._update_seat_status_from_active(seat_number)

        try:
            adm_dt = datetime.strptime(admission_date, "%Y-%m-%d").date()
            due_date = self._add_month(adm_dt).isoformat()
            notice_date = (
                datetime.strptime(due_date, "%Y-%m-%d").date()
                - timedelta(days=GRACE_PERIOD_DAYS)
            ).isoformat()
        except Exception:
            due_date = admission_date
            notice_date = None

        # Create fee record
        self.conn.execute(
            """
            INSERT INTO fees
                (student_id, monthly_fee, due_date, due_amount, next_due_date, notice_date)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (student_id, monthly_fee, due_date, due_date, notice_date),
        )
        self.conn.commit()
        return student_id

    def update_student(
        self,
        student_id,
        full_name,
        mobile_number,
        admission_date,
        monthly_fee,
        shift_type="FULL_DAY",
        photo_path: str = None,
    ):

        # Validate shift combination excluding the student being edited.
        # Also enforce that the seat being edited matches the current seat.
        row = self.get_student_by_id(student_id)
        if not row:
            return False, "Student not found."

        seat_number = row["seat_number"]
        ok, err = self._is_valid_shift_combination(
            seat_number,
            shift_type,
            editing_student_id=student_id,
        )
        if not ok:
            return False, err

        if photo_path is not None:
            self.conn.execute(
                "UPDATE students SET full_name=?, mobile_number=?, admission_date=?, shift_type=?, photo_path=? WHERE id=?",
                (
                    full_name,
                    mobile_number,
                    admission_date,
                    shift_type,
                    photo_path,
                    student_id,
                ),
            )
        else:
            self.conn.execute(
                "UPDATE students SET full_name=?, mobile_number=?, admission_date=?, shift_type=? WHERE id=?",
                (full_name, mobile_number, admission_date, shift_type, student_id),
            )

        self.conn.execute(
            "UPDATE fees SET monthly_fee=? WHERE student_id=?",
            (monthly_fee, student_id),
        )
        self._update_seat_status_from_active(seat_number)
        self.conn.commit()
        return True, "Student record updated."

    def mark_old_student(self, student_id, exit_date):
        row = self.conn.execute(
            "SELECT seat_number FROM students WHERE id=?", (student_id,)
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE students SET status='Old Student', exit_date=? WHERE id=?",
                (exit_date, student_id),
            )
            self.conn.execute(
                """
                UPDATE fee_notices
                SET status='Cancelled'
                WHERE student_id=? AND status='Pending'
                """,
                (student_id,),
            )
            self._update_seat_status_from_active(row["seat_number"])
            self.conn.commit()
            return True
        return False

    def get_all_students(self, status_filter=None):
        if status_filter:
            return self.conn.execute(
                "SELECT * FROM students WHERE status=? ORDER BY seat_number",
                (status_filter,),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM students ORDER BY seat_number"
        ).fetchall()

    def search_students(self, query):
        q = f"%{query}%"
        return self.conn.execute(
            "SELECT * FROM students WHERE full_name LIKE ? OR mobile_number LIKE ? OR seat_number LIKE ? "
            "ORDER BY seat_number",
            (q, q, q),
        ).fetchall()

    def get_student_photo_path(self, student_id: int) -> Optional[str]:
        row = self.conn.execute(
            "SELECT photo_path FROM students WHERE id=?", (student_id,)
        ).fetchone()
        if not row:
            return None
        return row["photo_path"]

    def set_student_photo_path(
        self, student_id: int, photo_path: Optional[str]
    ) -> None:
        self.conn.execute(
            "UPDATE students SET photo_path=? WHERE id=?", (photo_path, student_id)
        )
        self.conn.commit()

    def get_student_by_id(self, student_id):
        return self.conn.execute(
            "SELECT * FROM students WHERE id=?", (student_id,)
        ).fetchone()

    def count_students(self):
        active = self.conn.execute(
            "SELECT COUNT(*) FROM students WHERE status='Active'"
        ).fetchone()[0]
        old = self.conn.execute(
            "SELECT COUNT(*) FROM students WHERE status='Old Student'"
        ).fetchone()[0]
        return active, old

    # ── Fees ───────────────────────────────────
    def get_fees_with_students(self):
        return self.conn.execute("""
            SELECT s.seat_number, s.full_name, s.id as student_id,
                   f.id as fee_id, f.monthly_fee,
                   f.due_date, f.due_amount,
                   f.next_due_date, f.notice_date,
                   f.last_payment_date
            FROM students s
            JOIN fees f ON s.id = f.student_id
            WHERE s.status = 'Active'
            ORDER BY s.seat_number
        """).fetchall()

    def get_due_students(self):
        return self.conn.execute("""
            SELECT s.seat_number, s.full_name, f.due_amount
            FROM students s
            JOIN fees f ON s.id = f.student_id
            WHERE s.status='Active' AND f.due_amount > 0
            ORDER BY s.seat_number
        """).fetchall()

    def _advance_billing_cycle_if_needed(self, student_id: int, paid_due_date: str):
        """Backward-compatible wrapper for older callers."""
        self.mark_notice_paid(student_id, paid_due_date)
        self._advance_fee_cycle(student_id)

    def record_payment(self, student_id, amount, payment_date, notes=""):
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return False, "Payment amount must be a number."
        if amount <= 0:
            return False, "Payment amount must be greater than 0."

        fee = self.conn.execute(
            "SELECT * FROM fees WHERE student_id=?", (student_id,)
        ).fetchone()
        if not fee:
            return False, "Fee record not found."

        # Authoritative cycle due_date is the current fees.due_date.
        current_due_date = fee["due_date"]

        current_due = float(fee["due_amount"] or 0)
        if current_due <= 0:
            return False, "No due amount is currently payable for this student."

        new_due = max(0, current_due - amount)
        self.conn.execute(
            "UPDATE fees SET due_amount=?, last_payment_date=? WHERE student_id=?",
            (new_due, payment_date, student_id),
        )
        self.conn.execute(
            "INSERT INTO payment_history (student_id, amount, payment_date, notes) VALUES (?, ?, ?, ?)",
            (student_id, amount, payment_date, notes),
        )

        # If the cycle is fully settled, close current notices and advance even
        # when no notice was generated for this cycle.
        if float(new_due) <= 0 and current_due_date:
            self.mark_notice_paid(student_id, current_due_date)
            self._advance_fee_cycle(student_id)

        self.conn.commit()
        return True, f"Payment recorded. Remaining due: ₹{new_due:.0f}"

    def update_monthly_fee(self, student_id, monthly_fee, new_due=None):
        if new_due is not None:
            self.conn.execute(
                "UPDATE fees SET monthly_fee=?, due_amount=? WHERE student_id=?",
                (monthly_fee, new_due, student_id),
            )
        else:
            self.conn.execute(
                "UPDATE fees SET monthly_fee=? WHERE student_id=?",
                (monthly_fee, student_id),
            )
        self.conn.commit()

    def get_fee_record(self, student_id):
        return self.conn.execute(
            "SELECT * FROM fees WHERE student_id=?", (student_id,)
        ).fetchone()

    def get_payment_history(self, student_id=None):
        if student_id:
            return self.conn.execute(
                """
                SELECT ph.*, s.full_name, s.seat_number
                FROM payment_history ph
                JOIN students s ON ph.student_id = s.id
                WHERE ph.student_id=?
                ORDER BY ph.payment_date DESC
            """,
                (student_id,),
            ).fetchall()
        return self.conn.execute("""
            SELECT ph.*, s.full_name, s.seat_number
            FROM payment_history ph
            JOIN students s ON ph.student_id = s.id
            ORDER BY ph.payment_date DESC
        """).fetchall()

    # ── Export ─────────────────────────────────
    def export_students_csv(self, path):
        rows = self.conn.execute(
            "SELECT * FROM students ORDER BY seat_number"
        ).fetchall()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "ID",
                    "Seat Number",
                    "Full Name",
                    "Mobile Number",
                    "Admission Date",
                    "Exit Date",
                    "Status",
                ]
            )
            for r in rows:
                w.writerow(list(r))

    def export_fees_csv(self, path):
        rows = self.get_fees_with_students()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "Seat Number",
                    "Student Name",
                    "Monthly Fee",
                    "Due Date",
                    "Due Amount",
                    "Last Payment Date",
                ]
            )
            for r in rows:
                w.writerow(
                    [
                        r["seat_number"],
                        r["full_name"],
                        r["monthly_fee"],
                        r["due_date"],
                        r["due_amount"],
                        r["last_payment_date"],
                    ]
                )

    # ── Fee Subscription / Notices ──────────────────────────────────
    def _cycle_dates_for_student(self, student_id: int):
        """Return (next_due_date, notice_date) using subscription fields.

        next_due_date is computed/backfilled from students.admission_date.
        notice_date is computed/backfilled from fees.next_due_date.
        """
        row = self.conn.execute(
            """
            SELECT f.next_due_date, f.notice_date
            FROM fees f
            WHERE f.student_id=?
            """,
            (student_id,),
        ).fetchone()
        if not row:
            return None, None
        return row["next_due_date"], row["notice_date"]

    def _current_cycle_dates_for_student(self, student_id: int):
        """Return current fee cycle dates as a small dict, or None."""
        self._ensure_subscription_fields_for_student(student_id)
        row = self.conn.execute(
            """
            SELECT due_date, next_due_date, notice_date
            FROM fees
            WHERE student_id=?
            """,
            (student_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "due_date": row["due_date"],
            "next_due_date": row["next_due_date"],
            "notice_date": row["notice_date"],
        }

    def _add_month(self, dt: date) -> date:
        """Add 1 calendar month while keeping day when possible."""
        # Handle month rollover without external deps.
        year = dt.year + (dt.month // 12)
        month = (dt.month % 12) + 1
        # Clamp day to last day of target month.
        # February/leap-year safe.
        import calendar

        last_day = calendar.monthrange(year, month)[1]
        day = min(dt.day, last_day)
        return date(year, month, day)

    def _ensure_subscription_fields_for_student(self, student_id: int):
        """Fill missing fees.subscription fields for a student (no overwrites)."""
        row = self.conn.execute(
            """
            SELECT s.admission_date,
                   f.due_date,
                   f.next_due_date,
                   f.notice_date
            FROM students s
            LEFT JOIN fees f ON f.student_id = s.id
            WHERE s.id=?
            """,
            (student_id,),
        ).fetchone()
        if not row:
            return

        admission_date = row["admission_date"]
        if not admission_date:
            return

        try:
            adm_dt = datetime.strptime(admission_date, "%Y-%m-%d").date()
        except Exception:
            return

        next_due_date = row["next_due_date"]
        due_date = row["due_date"]
        notice_date = row["notice_date"]

        next_due_to_set = None
        if not next_due_date:
            next_due_to_set = self._add_month(adm_dt).isoformat()

        due_to_set = None
        if not due_date:
            due_to_set = (
                next_due_to_set or next_due_date or self._add_month(adm_dt).isoformat()
            )

        if next_due_to_set and not notice_date:
            # notice_date = next_due_date - GRACE_PERIOD_DAYS
            nd = datetime.strptime(next_due_to_set, "%Y-%m-%d").date()
            notice_to_set = (nd - timedelta(days=GRACE_PERIOD_DAYS)).isoformat()
        else:
            notice_to_set = None
            if not notice_date and next_due_date:
                try:
                    nd = datetime.strptime(next_due_date, "%Y-%m-%d").date()
                    notice_to_set = (nd - timedelta(days=GRACE_PERIOD_DAYS)).isoformat()
                except Exception:
                    notice_to_set = None

        # Apply only if missing.
        if next_due_to_set:
            self.conn.execute(
                "UPDATE fees SET next_due_date=? WHERE student_id=? AND (next_due_date IS NULL OR next_due_date='')",
                (next_due_to_set, student_id),
            )
        if due_to_set:
            self.conn.execute(
                "UPDATE fees SET due_date=? WHERE student_id=? AND (due_date IS NULL OR due_date='')",
                (due_to_set, student_id),
            )
        if notice_to_set:
            self.conn.execute(
                "UPDATE fees SET notice_date=? WHERE student_id=? AND (notice_date IS NULL OR notice_date='')",
                (notice_to_set, student_id),
            )

        # last_notice_generated: initialize if NULL.
        self.conn.execute(
            """
            UPDATE fees
            SET last_notice_generated = notice_date
            WHERE student_id=? AND (last_notice_generated IS NULL OR last_notice_generated='')
            """,
            (student_id,),
        )
        self.conn.commit()

    def _set_fee_cycle(self, student_id: int, due_date: str):
        """Set current fee cycle anchors to due_date and recompute notice_date."""
        try:
            due_dt = datetime.strptime(due_date, "%Y-%m-%d").date()
        except Exception:
            return False

        notice_date = (due_dt - timedelta(days=GRACE_PERIOD_DAYS)).isoformat()
        self.conn.execute(
            """
            UPDATE fees
            SET due_date=?,
                next_due_date=?,
                notice_date=?,
                last_notice_generated=NULL
            WHERE student_id=?
            """,
            (due_dt.isoformat(), due_dt.isoformat(), notice_date, student_id),
        )
        return True

    def _advance_fee_cycle(self, student_id: int):
        """Advance the current cycle by one calendar month and clear next-cycle due."""
        self._ensure_subscription_fields_for_student(student_id)
        row = self.conn.execute(
            "SELECT due_date, next_due_date FROM fees WHERE student_id=?",
            (student_id,),
        ).fetchone()
        if not row:
            return False

        current_due = row["due_date"] or row["next_due_date"]
        if not current_due:
            return False
        try:
            current_due_dt = datetime.strptime(current_due, "%Y-%m-%d").date()
        except Exception:
            return False

        new_due = self._add_month(current_due_dt).isoformat()
        if not self._set_fee_cycle(student_id, new_due):
            return False
        self.conn.execute(
            "UPDATE fees SET due_amount=0 WHERE student_id=?",
            (student_id,),
        )
        return True

    def mark_notice_paid(self, student_id, due_date):
        self.conn.execute(
            """
            UPDATE fee_notices
            SET status='Paid'
            WHERE student_id=? AND due_date=? AND status='Pending'
            """,
            (student_id, due_date),
        )

    def cancel_notice(self, notice_id):
        cur = self.conn.execute(
            """
            UPDATE fee_notices
            SET status='Cancelled'
            WHERE id=? AND status='Pending'
            """,
            (notice_id,),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def mark_notice_sent(self, notice_id):
        """Mark a fee notice as sent by saving the current timestamp."""
        self.conn.execute(
            """
            UPDATE fee_notices
            SET sent_at = datetime('now')
            WHERE id=?
            """,
            (notice_id,),
        )
        self.conn.commit()

    def get_notice_by_id(self, notice_id):
        return self.conn.execute(
            """
            SELECT fn.id,
                   fn.student_id,
                   fn.due_date,
                   fn.notice_date,
                   fn.message,
                   fn.status,
                   fn.created_at,
                   fn.sent_at,
                   s.full_name,
                   s.seat_number,
                   s.mobile_number,
                   s.status AS student_status,
                   f.monthly_fee,
                   f.due_amount
            FROM fee_notices fn
            JOIN students s ON s.id = fn.student_id
            LEFT JOIN fees f ON f.student_id = fn.student_id
            WHERE fn.id=?
            """,
            (notice_id,),
        ).fetchone()

    def get_notice_center_rows(self, status_filter=None):
        """Return notice rows with student/contact and current cycle context."""
        rows = self.conn.execute("""
            SELECT fn.id,
                   fn.student_id,
                   fn.due_date,
                   fn.notice_date,
                   fn.message,
                   fn.status,
                   fn.created_at,
                   fn.sent_at,
                   s.full_name,
                   s.seat_number,
                   s.mobile_number,
                   s.status AS student_status,
                   f.monthly_fee,
                   f.due_amount
            FROM fee_notices fn
            JOIN students s ON s.id = fn.student_id
            LEFT JOIN fees f ON f.student_id = fn.student_id
            ORDER BY fn.notice_date ASC, s.seat_number ASC
            """).fetchall()

        wanted = (status_filter or "All").strip()
        if not wanted or wanted == "All":
            return rows

        notice_statuses = {"Pending", "Paid", "Cancelled"}
        if wanted in notice_statuses:
            return [r for r in rows if r["status"] == wanted]

        cycle_statuses = {
            "Reminder Due",
            "Due",
            "Overdue",
            "Paid",
            "Active",
            "Cancelled",
        }
        if wanted in cycle_statuses:
            return [
                r
                for r in rows
                if r["status"] == "Pending"
                and self.get_fee_status(int(r["student_id"])) == wanted
            ]

        return rows

    def get_fee_status(self, student_id: int):
        """Return fee status for the *current cycle* (computed from fees fields).

        Business rules (final):
        - If student status != Active => Cancelled
        - If due_amount <= 0 => Paid
        - If notice_date <= today < due_date => Reminder Due
        - If due_date <= today <= due_date + GRACE_PERIOD_DAYS => Due
        - If today > due_date + GRACE_PERIOD_DAYS => Overdue
        """
        st_row = self.conn.execute(
            """
            SELECT s.status, f.due_date, f.due_amount, f.notice_date
            FROM students s
            JOIN fees f ON f.student_id=s.id
            WHERE s.id=?
            """,
            (student_id,),
        ).fetchone()

        if not st_row:
            return "Cancelled"

        student_status = st_row["status"]
        if student_status != "Active":
            return "Cancelled"

        due_date = st_row["due_date"]
        due_amount = st_row["due_amount"]
        notice_date = st_row["notice_date"]

        # If due_date missing, treat as Active (cannot compute windows).
        if not due_date:
            return "Active"

        today = date.today()
        try:
            due_dt = datetime.strptime(due_date, "%Y-%m-%d").date()
        except Exception:
            return "Active"

        # Parse notice_date if available.
        notice_dt = None
        if notice_date:
            try:
                notice_dt = datetime.strptime(notice_date, "%Y-%m-%d").date()
            except Exception:
                notice_dt = None

        if due_amount is None or float(due_amount) <= 0:
            if notice_dt is not None and today >= notice_dt:
                return "Active"
            return "Paid"

        # EXACT rule ordering required:
        # Reminder due window: notice_date <= today < due_date
        if notice_dt is not None and notice_dt <= today < due_dt:
            return "Reminder Due"

        # Due window: due_date <= today <= due_date + GRACE_PERIOD_DAYS
        grace_end = due_dt + timedelta(days=GRACE_PERIOD_DAYS)
        if due_dt <= today <= grace_end:
            return "Due"

        # Overdue strictly after due_dt + GRACE_PERIOD_DAYS
        if today > grace_end:
            return "Overdue"

        return "Active"

    def generate_fee_notices(self):
        """Generate fee reminder notices safely; safe to run repeatedly.

        Rules (final):
        - Generate only ONE notice per (student_id, due_date) billing cycle.
        - Never create notices for inactive students.
        - Open the payable cycle from monthly_fee when today reaches notice_date.
        - Notice text must include Dear {student_name} and the actual due_date.
        - Cancel any Pending notices for inactive/old students before processing.
        """
        today = date.today().isoformat()

        # Cancel pending notices for inactive students (old students never receive future reminders).
        self.conn.execute("""
            UPDATE fee_notices
            SET status='Cancelled'
            WHERE status='Pending'
              AND student_id IN (
                SELECT id FROM students WHERE status!='Active'
              )
            """)

        # Iterate active students and create notice for their current cycle (fees.due_date).
        active_students = self.conn.execute(
            "SELECT id FROM students WHERE status='Active' ORDER BY id"
        ).fetchall()

        for r in active_students:
            student_id = int(r["id"])

            # Ensure subscription fields exist.
            self._ensure_subscription_fields_for_student(student_id)

            # Fetch current cycle and student name.
            row = self.conn.execute(
                """
                SELECT
                    s.full_name AS full_name,
                    f.due_date AS due_date,
                    f.due_amount AS due_amount,
                    f.notice_date AS notice_date
                FROM students s
                JOIN fees f ON f.student_id=s.id
                WHERE s.id=?
                """,
                (student_id,),
            ).fetchone()
            if not row:
                continue

            due_date = row["due_date"]
            due_amount = row["due_amount"]
            notice_date = row["notice_date"]
            student_name = row["full_name"]

            if not due_date or not notice_date:
                continue

            # Only after reminder window starts.
            if today < notice_date:
                continue

            current_due = float(due_amount or 0)
            if current_due <= 0:
                monthly_fee = self.conn.execute(
                    "SELECT monthly_fee FROM fees WHERE student_id=?",
                    (student_id,),
                ).fetchone()
                next_due = float(monthly_fee["monthly_fee"] or 0) if monthly_fee else 0
                if next_due <= 0:
                    continue
                self.conn.execute(
                    "UPDATE fees SET due_amount=? WHERE student_id=?",
                    (next_due, student_id),
                )

            # Prevent duplicates (UNIQUE(student_id, due_date)).
            existing = self.conn.execute(
                """
                SELECT 1 FROM fee_notices
                WHERE student_id=? AND due_date=?
                LIMIT 1
                """,
                (student_id, due_date),
            ).fetchone()
            if existing:
                continue

            message = (
                f"Dear {student_name}, your monthly library subscription will expire on {due_date}. "
                "Please renew your subscription before the due date to avoid interruption of services."
            )

            self.conn.execute(
                """
                INSERT INTO fee_notices (student_id, due_date, notice_date, message, status, created_at)
                VALUES (?, ?, ?, ?, 'Pending', datetime('now'))
                """,
                (student_id, due_date, notice_date, message),
            )

        self.conn.commit()

    def get_pending_notice_count(self):
        """Return count of fee notices in Pending status."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM fee_notices WHERE status='Pending'"
        ).fetchone()
        return int(row["c"]) if row else 0

    def get_pending_notices(self):
        """Return pending notices ordered by notice_date ascending."""
        return self.conn.execute("""
            SELECT * FROM fee_notices
            WHERE status='Pending'
            ORDER BY notice_date ASC
            """).fetchall()

    def execute_raw_sql(self, sql, params=None):
        """Execute a raw SQL query and return rows. Used by remote client proxies."""
        cur = self.conn.cursor()
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return cur.fetchall()


# ── Remote Database Proxy Classes ─────────────────────────────────────────────

class RemoteDatabaseProxy:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.conn = RemoteConnectionProxy(self)

    def execute_raw_sql(self, sql, params=None):
        return self._make_call("execute_raw_sql", sql, params)

    def _make_call(self, name, *args, **kwargs):
        import requests
        headers = {"X-API-Key": self.api_key}
        payload = {"method": name, "args": args, "kwargs": kwargs}
        try:
            res = requests.post(f"{self.base_url}/api/db/call", json=payload, headers=headers, timeout=25)
            if res.status_code != 200:
                raise Exception(f"Server returned status {res.status_code}: {res.text}")
            data = res.json()
            if "error" in data:
                raise Exception(data["error"])
            return data["result"]
        except Exception as e:
            raise Exception(f"Database API call to {self.base_url} failed: {e}")

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        def method(*args, **kwargs):
            return self._make_call(name, *args, **kwargs)
        return method


class RemoteConnectionProxy:
    def __init__(self, proxy):
        self.proxy = proxy

    def execute(self, sql, params=None):
        rows = self.proxy.execute_raw_sql(sql, params)
        return RemoteCursorProxy(rows)


class RemoteCursorProxy:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows
