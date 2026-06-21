# TODO Stage 4.1 - Fee Automation (Subscription Renewal + Notices)

## Plan
1. **DB migrations (backward-compatible)** in `database/database.py`
   - Add migration-safe columns to `fees`:
     - `next_due_date TEXT`
     - `notice_date TEXT`
     - `last_notice_generated TEXT`
   - Create new table `fee_notices` with migration-safe creation.
   - Ensure migrations run automatically in `Database.__init__`.

2. **Notice generation system** in `database/database.py`
   - Implement helpers to parse dates and add months.
   - Implement `generate_fee_notices()` exactly as per rules:
     - only for Active students
     - only when `today >= notice_date`
     - only when current cycle unpaid (use `due_amount` + `next_due_date` / payment-history linkage)
     - prevent duplicates for the same due date

3. **Payment logic updates** in `database/database.py`
   - In `record_payment()`:
     - validate amount > 0
     - update due_amount (temporary, keep existing)
     - mark matching notice for that due cycle as Paid
     - advance next_due_date by one month
     - recompute notice_date
     - insert into payment_history

4. **Old student cancellation rules** in `mark_old_student()`
   - Cancel all pending notices for that student.

5. **Fees page update** in `pages/fees_page.py`
   - Add a new `📢 Fee Notices` button
   - Redesign FeesPage table columns to include:
     - Seat Number
     - Student Name
     - Monthly Fee
     - Due Amount
     - Next Due Date
     - Notice Date
     - Status
     - Last Payment Date
   - Add status mapping (Paid/Reminder Due/Overdue/Cancelled) using grace period.

6. **Call generate_fee_notices() automatically**
   - On app startup right after DB initialization (`app/main_window.py`)
   - On every Fees page `refresh()`.

7. **Dialogs / payments UI validation**
   - Ensure existing UI stays compatible.
   - Update message dialogs only if needed to reflect new validations.

## Progress
- [x] DB migrations + fee_notices table added
- [x] generate_fee_notices() implemented
- [x] record_payment() updated to advance next_due_date + mark notice Paid
- [x] mark_old_student() cancels pending notices and blocks future generation
- [x] Fees page refresh generates notices and shows Due Amount
- [x] Fee Notices center added with filters, details, copy actions, and cancellation
- [x] Dashboard shows pending/reminder/due/overdue notice counts
- [x] Fees page redesigned + startup notice generation completed
- [x] generate_fee_notices() called on startup and FeesPage.refresh()
- [x] Update UI/validation for payment rules
- [x] Compile + quick runtime sanity checks

## Business rules status
- [x] Grace period constant added (default 3 days)
- [x] Billing cycle fixed off admission_date (not payment date)
- [x] Notice generated exactly once per cycle (no duplicates)
- [x] Keep due_amount column temporarily for backward compatibility


