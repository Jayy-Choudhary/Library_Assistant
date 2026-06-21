import os
import sys
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from urllib.parse import quote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)

# Add repo root to path so 'database' and 'student_photo_utils' are importable
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from database.database import Database
from config.paths import DB_PATH, STUDENT_PHOTOS_DIR, API_KEY
from student_photo_utils import (
    ensure_dir,
    make_photo_filenames,
    resize_and_save_photo,
    validate_image_extension,
)

APP_ENV = os.getenv("APP_ENV", "development")
IS_PRODUCTION = APP_ENV == "production"

app = FastAPI(title="Library Assistant Web")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Ensure student_photos directory exists (may not after a fresh git clone)
os.makedirs(str(STUDENT_PHOTOS_DIR), exist_ok=True)

# Serve student photos from the existing folder at repo root.
app.mount(
    "/student_photos",
    StaticFiles(directory=str(STUDENT_PHOTOS_DIR)),
    name="student_photos",
)

# Static assets for templates
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)

db_path_env = os.getenv("DATABASE_PATH")
db = Database(db_path_env if db_path_env else DB_PATH)
try:
    db.generate_fee_notices()
except Exception:
    pass  # DB may be freshly created with no data yet

# ── Persistent Selenium WhatsApp driver ──────────────────────────────────────
_wa_driver = None

def _wa_get_or_create_driver():
    """Return a persistent Chrome WebDriver with a local profile (keeps WA Web logged in)."""
    if IS_PRODUCTION:
        raise Exception("WhatsApp Selenium Automation is disabled in the cloud environment.")
    global _wa_driver
    if _wa_driver is not None:
        try:
            _ = _wa_driver.title  # raises if browser was closed by user
            return _wa_driver
        except Exception:
            _wa_driver = None

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    options = Options()
    # Store the Chrome profile next to this file so login persists across restarts
    profile_dir = os.path.join(BASE_DIR, ".wa_chrome_profile")
    os.makedirs(profile_dir, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    _wa_driver = webdriver.Chrome(options=options)
    _wa_driver.maximize_window()
    return _wa_driver


def _render(request: Request, view: str, **context):
    context.setdefault("request", request)
    return templates.TemplateResponse(request, view, context)


@app.get("/app.css", include_in_schema=False)
def app_css():
    return FileResponse(os.path.join(BASE_DIR, "static", "app.css"))


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse(url="/dashboard")


# ── Dashboard ──────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    db.generate_fee_notices()
    total, occ, avail = db.seat_counts()
    active, _old = db.count_students()

    due_rows = db.get_due_students()
    pending_notices = db.get_pending_notice_count()
    reminder_due = len(db.get_notice_center_rows("Reminder Due"))
    due_notices = len(db.get_notice_center_rows("Due"))
    overdue_notices = len(db.get_notice_center_rows("Overdue"))

    return _render(
        request,
        "dashboard.html",
        total=total,
        occ=occ,
        avail=avail,
        active=active,
        pending_notices=pending_notices,
        reminder_due=reminder_due,
        due_notices=due_notices,
        overdue_notices=overdue_notices,
        due_rows=due_rows,
    )


# ── Students ──────────────────────────────────────────────────

@app.get("/students", response_class=HTMLResponse)
def students(request: Request, q: str = "", status_filter: str = "Active"):
    if status_filter == "All":
        rows = db.get_all_students()
    elif status_filter in ("Active", "Old Student"):
        rows = db.get_all_students(status_filter)
    else:
        rows = db.get_all_students("Active")

    if q.strip():
        rows = db.search_students(q.strip())

    return _render(
        request, "students.html", rows=rows, q=q, status_filter=status_filter
    )


@app.get("/students/{student_id}/profile", response_class=HTMLResponse)
def student_profile(request: Request, student_id: int):
    student = db.get_student_by_id(student_id)
    fee = db.get_fee_record(student_id)
    return _render(request, "student_profile.html", student=student, fee=fee)


@app.get("/students/add", response_class=HTMLResponse)
def students_add(request: Request):
    return _render(request, "student_form.html", student=None)


@app.post("/students/add")
async def students_add_post(
    request: Request,
    seat: str = Form(...),
    name: str = Form(...),
    mobile: str = Form(...),
    admission: str = Form(...),
    monthly_fee: float = Form(0.0),
    shift_type: str = Form("FULL_DAY"),
    photo: UploadFile | None = File(None),
):
    result = db.add_student(
        seat_number=seat,
        full_name=name,
        mobile_number=mobile,
        admission_date=admission,
        monthly_fee=monthly_fee,
        shift_type=shift_type,
    )

    if isinstance(result, tuple):
        return _render(
            request,
            "student_form.html",
            student=None,
            error=result[1],
        )

    student_id = int(result)

    if photo and photo.filename:
        repo_student_dir = str(STUDENT_PHOTOS_DIR)
        ensure_dir(repo_student_dir)
        tmp_path = os.path.join(repo_student_dir, "_upload_tmp")
        with open(tmp_path, "wb") as f:
            f.write(await photo.read())

        full_filename, thumb_filename = make_photo_filenames(
            name,
            seat or "00",
            mobile or "0000000000",
            tmp_path,
            photo_dir=repo_student_dir,
        )

        full_path = os.path.join(repo_student_dir, full_filename)
        thumb_path = os.path.join(repo_student_dir, thumb_filename)
        resize_and_save_photo(tmp_path, full_path, thumb_path)
        os.remove(tmp_path)
        db.set_student_photo_path(student_id, full_path)

    return RedirectResponse(url="/students", status_code=303)


@app.get("/students/{student_id}/edit", response_class=HTMLResponse)
def students_edit(request: Request, student_id: int):
    student = db.get_student_by_id(student_id)
    fee = db.get_fee_record(student_id)
    return _render(request, "student_form.html", student=student, fee=fee)


@app.post("/students/{student_id}/edit")
async def students_edit_post(
    request: Request,
    student_id: int,
    seat: str = Form(...),
    name: str = Form(...),
    mobile: str = Form(...),
    admission: str = Form(...),
    monthly_fee: float = Form(0.0),
    shift_type: str = Form("FULL_DAY"),
    photo: UploadFile | None = File(None),
    remove_photo: str = Form("off"),
):
    photo_path = None
    if remove_photo == "on":
        db.set_student_photo_path(student_id, None)

    if photo and photo.filename:
        repo_student_dir = str(STUDENT_PHOTOS_DIR)
        ensure_dir(repo_student_dir)
        tmp_path = os.path.join(repo_student_dir, "_upload_tmp")
        with open(tmp_path, "wb") as f:
            f.write(await photo.read())

        full_filename, thumb_filename = make_photo_filenames(
            name,
            seat or "00",
            mobile or "0000000000",
            tmp_path,
            photo_dir=repo_student_dir,
        )

        full_path = os.path.join(repo_student_dir, full_filename)
        thumb_path = os.path.join(repo_student_dir, thumb_filename)
        resize_and_save_photo(tmp_path, full_path, thumb_path)
        os.remove(tmp_path)
        photo_path = full_path

    ok = db.update_student(
        student_id=student_id,
        full_name=name,
        mobile_number=mobile,
        admission_date=admission,
        monthly_fee=monthly_fee,
        shift_type=shift_type,
        photo_path=photo_path,
    )

    if isinstance(ok, tuple) and ok[0] is False:
        return _render(
            request,
            "student_form.html",
            student=db.get_student_by_id(student_id),
            error=ok[1],
        )

    return RedirectResponse(url="/students", status_code=303)


@app.post("/students/{student_id}/mark-old")
def students_mark_old(request: Request, student_id: int, exit_date: str = Form(...)):
    db.mark_old_student(student_id, exit_date)
    return RedirectResponse(url="/students", status_code=303)


# ── Seats ─────────────────────────────────────────────────────

@app.get("/seats", response_class=HTMLResponse)
def seats(request: Request, room_filter: str = "All"):
    rows = db.get_all_seats()

    f = (room_filter or "All").strip().upper()
    if f not in ("ALL", "A", "B", "C"):
        f = "ALL"

    active_rows = db.conn.execute(
        "SELECT seat_number, shift_type FROM students WHERE status='Active'"
    ).fetchall()
    active_by_seat = {}
    for ar in active_rows:
        seat_number = ar["seat_number"]
        shift_type = ar["shift_type"] if ar["shift_type"] else "FULL_DAY"
        active_by_seat.setdefault(seat_number, []).append(shift_type)

    table = []
    for r in rows:
        seat_room = (r["room"] or "A").strip().upper() if "room" in r.keys() else "A"
        if f != "ALL" and seat_room != f:
            continue

        seat_number = r["seat_number"]
        shifts = active_by_seat.get(seat_number, [])

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

        table.append(
            {
                "seat_number": seat_number,
                "room": seat_room,
                "display_status": display_status,
                "tag": tag,
            }
        )

    return _render(request, "seats.html", rows=table, room_filter=room_filter)


@app.post("/seats/add")
def seats_add_post(
    request: Request,
    room: str = Form(...),
    prefix: str = Form(...),
    start: int = Form(...),
    end: int = Form(...),
):
    added, skipped = db.add_seats_bulk(prefix, start, end, room=room)
    return RedirectResponse(url=f"/seats?room_filter={room}", status_code=303)


# ── Fees ──────────────────────────────────────────────────────

@app.get("/fees", response_class=HTMLResponse)
def fees(request: Request, filter: str = "All"):
    db.generate_fee_notices()
    rows = db.get_fees_with_students()

    fee_rows = []
    for r in rows:
        student_id = int(r["student_id"])
        status = db.get_fee_status(student_id)

        if filter == "Due Only" and status not in ("Reminder Due", "Due", "Overdue"):
            continue

        fee_rows.append({
            "student_id": student_id,
            "seat_number": r["seat_number"],
            "full_name": r["full_name"],
            "monthly_fee": f"₹{r['monthly_fee']:.0f}" if r['monthly_fee'] else "₹0",
            "due_amount": f"₹{r['due_amount']:.0f}" if r['due_amount'] else "₹0",
            "due_amount_raw": r['due_amount'] or 0,
            "next_due_date": r["next_due_date"] or "—",
            "notice_date": r["notice_date"] or "—",
            "status": status,
            "last_payment_date": r["last_payment_date"] or "—",
        })

    pending_notices = db.get_pending_notice_count()

    return _render(
        request, "fees.html",
        rows=fee_rows,
        filter=filter,
        pending_notices=pending_notices,
    )


@app.post("/fees/{student_id}/pay")
def fees_pay(
    request: Request,
    student_id: int,
    amount: float = Form(...),
    payment_date: str = Form(...),
    notes: str = Form(""),
):
    student = db.get_student_by_id(student_id)
    fee = db.get_fee_record(student_id)
    if not student or not fee:
        return _render(
            request, "fees.html",
            rows=[],
            filter="All",
            pending_notices=db.get_pending_notice_count(),
            error="Student or fee record not found.",
        )

    ok, msg = db.record_payment(student_id, amount, payment_date, notes)
    if ok:
        return RedirectResponse(url="/fees", status_code=303)
    else:
        return _render(
            request,
            "student_fee_pay.html",
            student=student,
            fee=fee,
            error=msg,
        )


@app.get("/fees/{student_id}/pay", response_class=HTMLResponse)
def fees_pay_form(request: Request, student_id: int):
    student = db.get_student_by_id(student_id)
    fee = db.get_fee_record(student_id)
    return _render(request, "student_fee_pay.html", student=student, fee=fee)


@app.post("/fees/{student_id}/update")
def fees_update(
    request: Request,
    student_id: int,
    monthly_fee: float = Form(...),
    due_amount: float = Form(...),
):
    db.update_monthly_fee(student_id, monthly_fee, due_amount)
    return RedirectResponse(url="/fees", status_code=303)


@app.get("/fees/{student_id}/update", response_class=HTMLResponse)
def fees_update_form(request: Request, student_id: int):
    student = db.get_student_by_id(student_id)
    fee = db.get_fee_record(student_id)
    return _render(request, "student_fee_update.html", student=student, fee=fee)


@app.get("/fees/{student_id}/history", response_class=HTMLResponse)
def fees_history(request: Request, student_id: int):
    student = db.get_student_by_id(student_id)
    rows = db.get_payment_history(student_id)
    return _render(request, "payment_history.html", student=student, rows=rows)


# ── Fee Notices ────────────────────────────────────────────────

@app.get("/fees/notices", response_class=HTMLResponse)
def fee_notices(request: Request, filter: str = "Pending"):
    db.generate_fee_notices()
    rows = db.get_notice_center_rows(filter)
    return _render(request, "fee_notices.html", rows=rows, filter=filter, error=None)


@app.get("/fees/notices/pending-all")
def fee_notices_pending_all():
    """Return all pending notices as JSON for the bulk send modal."""
    from fastapi.responses import JSONResponse
    rows = db.get_notice_center_rows("Pending")
    result = []
    for row in rows:
        mobile = _normalize_wa_mobile(row["mobile_number"])
        due_amount = float(row["due_amount"] or 0)
        wa_text = _build_wa_message(row)
        wa_url = f"https://wa.me/{mobile}?text={quote(wa_text)}" if mobile else None
        result.append({
            "id": row["id"],
            "full_name": row["full_name"] or "",
            "seat_number": row["seat_number"] or "",
            "mobile_number": row["mobile_number"] or "",
            "due_date": row["due_date"] or "",
            "due_amount": due_amount,
            "whatsapp_text": wa_text,
            "wa_url": wa_url,
            "has_valid_mobile": mobile is not None,
            "sent_at": row["sent_at"] or "",
        })
    return JSONResponse(result)


@app.get("/fees/notices/whatsapp-open")
def whatsapp_open():
    """Open (or focus) WhatsApp Web in the persistent Selenium browser."""
    from fastapi.responses import JSONResponse
    try:
        driver = _wa_get_or_create_driver()
        if "web.whatsapp.com" not in driver.current_url:
            driver.get("https://web.whatsapp.com")
        driver.execute_script("window.focus();")
        return JSONResponse({"status": "opened"})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


@app.get("/fees/notices/whatsapp-status")
def whatsapp_status():
    """Check if WhatsApp Web is open and logged in."""
    from fastapi.responses import JSONResponse
    if IS_PRODUCTION:
        return JSONResponse({"linked": False, "reason": "Disabled in cloud mode", "is_production": True})
    global _wa_driver
    if _wa_driver is None:
        return JSONResponse({"linked": False, "reason": "Browser not opened", "is_production": False})
    try:
        _wa_driver.title  # will raise if browser closed
        url = _wa_driver.current_url
        if "web.whatsapp.com" not in url:
            return JSONResponse({"linked": False, "reason": "Not on WhatsApp Web", "is_production": False})
        # Check for QR code page vs logged-in state
        page_src = _wa_driver.page_source
        if 'data-testid="qrcode"' in page_src or 'qrcode' in page_src:
            return JSONResponse({"linked": False, "reason": "Waiting for QR scan", "is_production": False})
        if "pane-side" not in page_src and "chat-list" not in page_src:
            return JSONResponse({"linked": False, "reason": "Loading WhatsApp Web...", "is_production": False})
        return JSONResponse({"linked": True, "is_production": False})
    except Exception as e:
        _wa_driver = None
        return JSONResponse({"linked": False, "reason": str(e), "is_production": False})


@app.get("/fees/notices/debug-dom")
def debug_dom():
    """Inspect elements on the active WhatsApp Web page for diagnostics."""
    from fastapi.responses import JSONResponse
    global _wa_driver
    if _wa_driver is None:
        return JSONResponse({"status": "no driver"})
    try:
        results = {}
        page_src = _wa_driver.page_source
        results["has_landing"] = "Landing" in page_src
        results["has_qrcode"] = 'data-testid="qrcode"' in page_src or 'qrcode' in page_src
        results["has_pane_side"] = "pane-side" in page_src or "pane-side" in page_src
        results["has_chat_list"] = "chat-list" in page_src
        results["page_src_len"] = len(page_src)
        results["page_src_prefix"] = page_src[:500]
        
        # Try various search box XPaths
        search_xpaths = {
            "old_data_tab_3": '//div[@contenteditable="true"][@data-tab="3"]',
            "aria_label_search": '//div[@aria-label="Search input textbox"]',
            "title_search": '//div[@title="Search input textbox"]',
            "role_textbox": '//div[@role="textbox"]',
            "any_contenteditable": '//div[@contenteditable="true"]'
        }
        for name, xpath in search_xpaths.items():
            elements = _wa_driver.find_elements("xpath", xpath)
            results[name] = {
                "count": len(elements),
                "samples": [el.get_attribute("outerHTML")[:250] for el in elements[:3]]
            }
        # Also check current URL
        results["current_url"] = _wa_driver.current_url
        return JSONResponse(results)
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.get("/fees/notices/dump-html")
def dump_html():
    """Write the page source of the active WhatsApp Web window to a local file."""
    from fastapi.responses import JSONResponse
    global _wa_driver
    if _wa_driver is None:
        return JSONResponse({"status": "no driver"})
    try:
        path = r"C:\Users\jugal\.gemini\antigravity-ide\brain\0a232974-7c2e-4422-9b53-ae949d4843ca\scratch\whatsapp_page.html"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_wa_driver.page_source)
        return JSONResponse({"status": "dumped", "path": path})
    except Exception as e:
        return JSONResponse({"error": str(e)})



@app.get("/fees/notices/send-bulk-stream")
async def fee_notices_send_bulk_stream():
    """SSE: automated Selenium bulk sending — ONE persistent browser session, no reload between students."""
    import asyncio
    import json as _json
    import time

    async def generate():
        rows = db.get_notice_center_rows("Pending")
        total = len(rows)
        sent = 0
        failed = 0

        yield f"data: {_json.dumps({'type': 'start', 'total': total})}\n\n"

        if total == 0:
            yield f"data: {_json.dumps({'type': 'done', 'sent': 0, 'failed': 0, 'total': 0})}\n\n"
            return

        # Get / create persistent driver
        try:
            driver = await asyncio.to_thread(_wa_get_or_create_driver)
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'index': 0, 'total': total, 'name': 'Browser', 'error': f'Could not open browser: {str(e)[:80]}' })}\n\n"
            yield f"data: {_json.dumps({'type': 'done', 'sent': 0, 'failed': total, 'total': total})}\n\n"
            return

        # Make sure we are on WhatsApp Web
        def ensure_wa():
            if "web.whatsapp.com" not in driver.current_url:
                driver.get("https://web.whatsapp.com")
                time.sleep(6)   # wait for WA to load
        await asyncio.to_thread(ensure_wa)

        yield f"data: {_json.dumps({'type': 'wa_ready'})}\n\n"

        for i, row in enumerate(rows, 1):
            mobile = _normalize_wa_mobile(row["mobile_number"])
            name   = row["full_name"] or "Unknown"

            if not mobile:
                failed += 1
                yield f"data: {_json.dumps({'type': 'skip', 'index': i, 'total': total, 'name': name, 'reason': 'Invalid mobile number'})}\n\n"
                continue

            yield f"data: {_json.dumps({'type': 'sending', 'index': i, 'total': total, 'name': name})}\n\n"

            def send_one(mobile=mobile, row=row):
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.common.keys import Keys
                import pyperclip

                wait = WebDriverWait(driver, 15)

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
                            errors.append(f"{xpath}: {str(e)[:45]}")
                    raise Exception(f"Could not find {name}. Errors: {'; '.join(errors)}")

                # ── Step 1: Click the search box in the left sidebar ──────────
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
                # Clear any previous search
                search_box.send_keys(Keys.CONTROL + "a")
                search_box.send_keys(Keys.DELETE)
                search_box.send_keys(Keys.ESCAPE)
                time.sleep(0.3)

                # ── Step 2: Type the phone number and wait dynamically ────────
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

                # ── Step 3: Click the search result ───────────────────────────
                driver.execute_script("arguments[0].scrollIntoView(true);", first_result)
                time.sleep(0.3)
                try:
                    first_result.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", first_result)
                time.sleep(1.2)

                # ── Step 4: Find the message input and paste message ──────────
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

                # Paste via clipboard (handles newlines, emojis, special chars)
                msg = _build_wa_message(row)
                pyperclip.copy(msg)
                msg_input.send_keys(Keys.CONTROL + "v")
                time.sleep(0.6)

                # ── Step 5: Send ──────────────────────────────────────────────
                msg_input.send_keys(Keys.ENTER)
                time.sleep(1.2)   # let the send animation complete

            try:
                await asyncio.to_thread(send_one)
                sent += 1
                yield f"data: {_json.dumps({'type': 'sent', 'index': i, 'total': total, 'name': name})}\n\n"
            except Exception as e:
                err_msg = str(e)
                if "NOT_ON_WHATSAPP" in err_msg:
                    yield f"data: {_json.dumps({'type': 'skip', 'index': i, 'total': total, 'name': name, 'reason': 'Number is not on WhatsApp'})}\n\n"
                else:
                    failed += 1
                    yield f"data: {_json.dumps({'type': 'error', 'index': i, 'total': total, 'name': name, 'error': err_msg[:100]})}\n\n"

        yield f"data: {_json.dumps({'type': 'done', 'sent': sent, 'failed': failed, 'total': total})}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/fees/notices/{notice_id}/cancel")
def fee_notice_cancel(request: Request, notice_id: int):
    db.cancel_notice(notice_id)
    return RedirectResponse(url="/fees/notices", status_code=303)


@app.post("/fees/notices/{notice_id}/mark-sent")
def fee_notice_mark_sent(notice_id: int):
    """Mark a notice as sent (update sent_at timestamp)."""
    from fastapi.responses import JSONResponse
    db.mark_notice_sent(notice_id)
    return JSONResponse({"status": "success"})


@app.post("/api/db/call")
async def db_call(request: Request):
    """Secure endpoint for desktop/remote clients to run database methods."""
    from fastapi.responses import JSONResponse
    
    # 1. Authorize using headers
    client_key = request.headers.get("X-API-Key")
    if client_key != API_KEY:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        
    method_name = body.get("method")
    args = body.get("args", [])
    kwargs = body.get("kwargs", {})
    
    if not method_name or method_name.startswith("_"):
        return JSONResponse({"error": "Invalid method name"}, status_code=400)
        
    method = getattr(db, method_name, None)
    if not method:
        return JSONResponse({"error": f"Method {method_name} not found"}, status_code=404)
        
    try:
        # Run method locally
        result = method(*args, **kwargs)
        
        # Serialize result (resolves sqlite3.Row and tuple types)
        def serialize_item(val):
            import sqlite3
            if isinstance(val, list):
                return [serialize_item(x) for x in val]
            if isinstance(val, sqlite3.Row):
                return dict(val)
            if isinstance(val, tuple):
                return [serialize_item(x) for x in val]
            return val
            
        return JSONResponse({"result": serialize_item(result)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/student-photo/upload")
async def student_photo_upload(
    request: Request,
    student_id: int = Form(...),
    photo: UploadFile = File(...),
):
    """Secure endpoint for mobile app to upload a student photo."""
    from fastapi.responses import JSONResponse

    client_key = request.headers.get("X-API-Key")
    if client_key != API_KEY:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Verify student exists
    student = db.get_student_by_id(student_id)
    if student is None:
        return JSONResponse({"error": "Student not found"}, status_code=404)

    # Validate file extension
    ok, err = validate_image_extension(photo.filename or "")
    if not ok:
        return JSONResponse({"error": err}, status_code=400)

    repo_student_dir = str(STUDENT_PHOTOS_DIR)
    ensure_dir(repo_student_dir)

    tmp_path = os.path.join(repo_student_dir, "_upload_tmp_api")
    with open(tmp_path, "wb") as f:
        f.write(await photo.read())

    try:
        name = student["full_name"] or "Student"
        seat = student["seat_number"] or "00"
        mobile = student["mobile_number"] or "0000000000"

        full_filename, thumb_filename = make_photo_filenames(
            name, seat, mobile, tmp_path, photo_dir=repo_student_dir,
        )

        full_path = os.path.join(repo_student_dir, full_filename)
        thumb_path = os.path.join(repo_student_dir, thumb_filename)
        resize_and_save_photo(tmp_path, full_path, thumb_path)
        db.set_student_photo_path(student_id, full_path)

        return JSONResponse({
            "success": True,
            "filename": full_filename,
            "thumb_filename": thumb_filename,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/api/db/download")
def db_download(request: Request):
    """Secure endpoint to download the SQLite database file."""
    from fastapi.responses import JSONResponse
    client_key = request.headers.get("X-API-Key")
    if client_key != API_KEY:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    db_file_path = db_path_env if db_path_env else DB_PATH
    if not os.path.exists(db_file_path):
        return JSONResponse({"error": "Database file not found"}, status_code=404)
        
    # Flush any server-side database WAL cache back to the main database file before serving the download
    try:
        db.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass

    return FileResponse(
        db_file_path,
        media_type="application/octet-stream",
        filename="library_assistant.db"
    )


@app.post("/api/db/upload")
async def db_upload(request: Request, file: UploadFile = File(...)):
    """Secure endpoint to upload and replace the SQLite database file."""
    from fastapi.responses import JSONResponse
    client_key = request.headers.get("X-API-Key")
    if client_key != API_KEY:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    db_file_path = db_path_env if db_path_env else DB_PATH
    
    global db
    try:
        # Close the local database connection in the web app before overwriting the file
        db.conn.close()
    except Exception:
        pass
        
    try:
        # Delete WAL and SHM files to prevent SQLite recovery conflicts with the new database file
        for ext in ("-wal", "-shm"):
            extra_file = str(db_file_path) + ext
            if os.path.exists(extra_file):
                try:
                    os.remove(extra_file)
                except Exception:
                    pass

        # Overwrite the database file
        with open(db_file_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        # Re-initialize the local database connection
        db = Database(db_file_path)

        # Touch PythonAnywhere's WSGI configuration to trigger programmatic reload,
        # forcing all workers to discard connection cache and reload the new database file.
        wsgi_file = "/var/www/jaychoudhary_pythonanywhere_com_wsgi.py"
        if os.path.exists(wsgi_file):
            try:
                os.utime(wsgi_file, None)
            except Exception:
                pass

        return JSONResponse({"status": "success", "message": "Database uploaded and replaced successfully"})
    except Exception as e:
        # Re-initialize even on failure to avoid a broken application state
        db = Database(db_file_path)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/fees/export")
def fees_export(request: Request):
    from fastapi.responses import PlainTextResponse
    import csv, io

    rows = db.get_fees_with_students()
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow([
        "Seat Number", "Student Name", "Monthly Fee",
        "Due Date", "Due Amount", "Last Payment Date"
    ])
    for r in rows:
        w.writerow([
            r["seat_number"],
            r["full_name"],
            r["monthly_fee"],
            r["due_date"],
            r["due_amount"],
            r["last_payment_date"],
        ])
    return PlainTextResponse(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fees.csv"},
    )


# ── Rooms ──────────────────────────────────────────────────────

@app.get("/rooms", response_class=HTMLResponse)
def rooms(request: Request, room_filter: str = "ALL"):

    rooms_list = ["A", "B", "C"]
    seats_cache = list(db.get_all_seats())

    active_students = list(db.conn.execute("""
            SELECT s.id AS student_id,
                   s.full_name AS full_name,
                   s.mobile_number AS mobile_number,
                   s.seat_number AS seat_number,
                   s.shift_type AS shift_type,
                   COALESCE(f.due_amount, 0) AS due_amount
            FROM students s
            LEFT JOIN (
                SELECT student_id, COALESCE(SUM(due_amount),0) AS due_amount
                FROM fees
                GROUP BY student_id
            ) f ON f.student_id = s.id
            WHERE s.status='Active'
            """).fetchall())

    grouped = {}
    for s in active_students:
        grouped.setdefault(s["seat_number"], []).append(s)

    layout_cache = {r: db.get_room_layout(r) for r in rooms_list}

    def compute_state(seat_students):
        details = []
        for s in seat_students:
            st = s["shift_type"] if s["shift_type"] else "FULL_DAY"
            st_label = {
                "FULL_DAY": "Full Day",
                "HALF_DAY_DAY": "Half Day (Day)",
                "HALF_DAY_NIGHT": "Half Day (Night)",
            }.get(st, "Full Day")
            details.append({
                "full_name": s["full_name"],
                "mobile_number": s["mobile_number"],
                "shift": st_label,
                "due_amount": float(s["due_amount"] or 0)
            })

        if not seat_students:
            return {"color": "#22C55E", "names": [], "details": []}
        shifts = [
            s["shift_type"] if s["shift_type"] else "FULL_DAY" for s in seat_students
        ]
        if "FULL_DAY" in shifts:
            return {
                "color": "#EF4444",
                "names": [s["full_name"] for s in seat_students],
                "details": details,
            }
        if (
            len(seat_students) == 2
            and "HALF_DAY_DAY" in shifts
            and "HALF_DAY_NIGHT" in shifts
        ):
            return {
                "color": "#2563EB",
                "names": [s["full_name"] for s in seat_students],
                "details": details,
            }
        if len(seat_students) == 1 and shifts[0] in ("HALF_DAY_DAY", "HALF_DAY_NIGHT"):
            return {"color": "#6B7280", "names": [seat_students[0]["full_name"]], "details": details}
        return {"color": "#6B7280", "names": [s["full_name"] for s in seat_students], "details": details}

    room_filter_norm = (room_filter or "ALL").strip().upper()
    if room_filter_norm not in ("ALL", "A", "B", "C"):
        room_filter_norm = "ALL"

    all_tiles = []
    target_rooms = rooms_list if room_filter_norm == "ALL" else [room_filter_norm]

    for room in target_rooms:
        _, columns, seat_spacing = layout_cache[room]
        columns = max(1, int(columns))
        seat_spacing = max(0, int(seat_spacing))

        seats_in_room = [
            r["seat_number"]
            for r in seats_cache
            if ((r["room"] or "A").strip().upper() == room)
        ]
        seats_in_room = sorted(seats_in_room)

        tiles = []
        for seat_number in seats_in_room:
            st = compute_state(grouped.get(seat_number, []))
            tiles.append(
                {
                    "seat_number": seat_number,
                    "color": st["color"],
                    "names": st["names"],
                    "details": st["details"],
                    "row": None,
                    "col": None,
                }
            )

        for i, t in enumerate(tiles):
            t["row"] = i // columns
            t["col"] = i % columns

        all_tiles.append(
            {
                "room": room,
                "columns": columns,
                "seat_spacing": seat_spacing,
                "tiles": tiles,
            }
        )

    return _render(
        request, "rooms.html", room_filter=room_filter_norm, all_tiles=all_tiles
    )


@app.post("/rooms/layout")
def rooms_layout_post(
    request: Request,
    room: str = Form(...),
    rows: int = Form(...),
    columns: int = Form(...),
    seat_spacing: int = Form(8),
):
    db.set_room_layout(room, rows, columns, seat_spacing)
    return RedirectResponse(url=f"/rooms?room_filter={room}", status_code=303)


# ── WhatsApp Fee Notices ───────────────────────────────────────

def _normalize_wa_mobile(mobile_number: str) -> str | None:
    """Normalize to 12-digit Indian number (91XXXXXXXXXX) or return None."""
    raw = str(mobile_number or "").strip()
    normalized = "".join(ch for ch in raw if ch.isdigit())
    if len(normalized) == 10:
        return f"91{normalized}"
    if len(normalized) == 12 and normalized.startswith("91"):
        return normalized
    return None


def _build_wa_message(row) -> str:
    due_amount = float(row["due_amount"] or 0)
    return (
        f"Student: {row['full_name']}\n"
        f"Seat Number: {row['seat_number']}\n"
        f"Due Date: {row['due_date']}\n"
        f"Due Amount: Rs. {due_amount:.0f}\n\n"
        f"{row['message'] or ''}"
    )


@app.get("/fees/notices/{notice_id}/whatsapp")
def fee_notice_whatsapp(request: Request, notice_id: int):
    """Redirect directly to WhatsApp Web/App with the pre-filled fee notice message."""
    row = db.get_notice_by_id(notice_id)
    if not row:
        rows = db.get_notice_center_rows("Pending")
        return _render(request, "fee_notices.html", rows=rows, filter="Pending",
                       error="Notice not found.")

    mobile = _normalize_wa_mobile(row["mobile_number"])
    if not mobile:
        rows = db.get_notice_center_rows("Pending")
        return _render(request, "fee_notices.html", rows=rows, filter="Pending",
                       error=f"Invalid mobile number for {row['full_name']}. "
                             "WhatsApp requires a valid 10-digit Indian number.")

    # Mark notice as sent in database
    db.mark_notice_sent(notice_id)

    message = _build_wa_message(row)
    wa_url = f"https://wa.me/{mobile}?text={quote(message)}"
    return RedirectResponse(url=wa_url, status_code=303)




@app.get("/fees/notices/{notice_id}/message")
def fee_notice_message_api(notice_id: int):
    """Return notice message text as JSON for the client-side preview panel."""
    from fastapi.responses import JSONResponse
    row = db.get_notice_by_id(notice_id)
    if not row:
        return JSONResponse({"message": "", "whatsapp_text": "", "full_name": "", "mobile_number": ""})
    return JSONResponse({
        "message": row["message"] or "",
        "whatsapp_text": _build_wa_message(row),
        "full_name": row["full_name"] or "",
        "mobile_number": row["mobile_number"] or "",
    })


# ── WSGI Middleware wrapper for PythonAnywhere ────────────────────────────────
# Custom adapter: converts ASGI (FastAPI) → WSGI without background threads.
# a2wsgi uses threads that hang on PythonAnywhere, so we roll our own.
import asyncio

def _make_wsgi_app(asgi_app):
    """Wrap an ASGI app as a WSGI callable — no threads, no hanging."""

    def wsgi_app(environ, start_response):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                _asgi_to_wsgi(asgi_app, environ, start_response)
            )
        finally:
            loop.close()

    return wsgi_app


async def _asgi_to_wsgi(asgi_app, environ, start_response):
    """Run a single ASGI request→response cycle synchronously."""

    # ── Build ASGI scope from WSGI environ ─────────────────────────────
    http_version = environ.get("SERVER_PROTOCOL", "HTTP/1.1").split("/", 1)[-1]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": http_version,
        "method": environ["REQUEST_METHOD"],
        "path": environ.get("PATH_INFO", "/"),
        "query_string": environ.get("QUERY_STRING", "").encode("latin-1"),
        "root_path": environ.get("SCRIPT_NAME", ""),
        "scheme": environ.get("wsgi.url_scheme", "http"),
        "server": (
            environ.get("SERVER_NAME", "localhost"),
            int(environ.get("SERVER_PORT", "80")),
        ),
        "headers": _environ_to_headers(environ),
    }

    # ── Read request body ──────────────────────────────────────────────
    try:
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
    except (ValueError, TypeError):
        content_length = 0
    body = environ["wsgi.input"].read(content_length) if content_length > 0 else b""

    body_sent = False

    async def receive():
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        # After body is sent, wait for disconnect (which won't happen in WSGI)
        await asyncio.sleep(3600)
        return {"type": "http.disconnect"}

    # ── Collect response ───────────────────────────────────────────────
    status_code = 200
    response_headers = []
    body_parts = []

    async def send(message):
        nonlocal status_code, response_headers
        msg_type = message["type"]
        if msg_type == "http.response.start":
            status_code = message["status"]
            response_headers = [
                (k.decode("latin-1"), v.decode("latin-1"))
                for k, v in message.get("headers", [])
            ]
        elif msg_type == "http.response.body":
            chunk = message.get("body", b"")
            if chunk:
                body_parts.append(chunk)

    await asgi_app(scope, receive, send)

    # Map status code to reason phrase
    from http.client import responses as http_reasons
    reason = http_reasons.get(status_code, "Unknown")
    start_response(f"{status_code} {reason}", response_headers)
    return body_parts


def _environ_to_headers(environ):
    """Extract HTTP headers from WSGI environ into ASGI format."""
    headers = []
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            name = key[5:].lower().replace("_", "-")
            headers.append((name.encode("latin-1"), value.encode("latin-1")))
        elif key == "CONTENT_TYPE":
            headers.append((b"content-type", value.encode("latin-1")))
        elif key == "CONTENT_LENGTH":
            headers.append((b"content-length", value.encode("latin-1")))
    return headers


wsgi_app = _make_wsgi_app(app)


