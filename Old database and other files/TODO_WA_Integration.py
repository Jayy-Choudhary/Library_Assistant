"""
TODO: WhatsApp Integration for Fee Notice Center

Purpose
-------
This file is a planning handoff for adding WhatsApp message integration to the
existing Tkinter + SQLite Library Assistant app.

Do not implement automatically from this file unless explicitly requested.
Use the existing Fee Notice Center and database helper patterns.


Main goal
---------
Allow staff to send or open prefilled WhatsApp fee notice messages for students
from the Fee Notice Center.

The first implementation should be simple, safe, and dependency-free:

- Build a WhatsApp-ready message from the selected notice.
- Normalize Indian mobile numbers to WhatsApp `wa.me` format.
- Open the system browser with a prefilled WhatsApp URL.
- Keep the existing clipboard copy actions.
- Avoid storing WhatsApp delivery status unless a future API-based integration
  is added.


Recommended scope
-----------------
Phase 1 should use WhatsApp click-to-chat URLs only:

    https://wa.me/91{mobile_number}?text={urlencoded_message}

This opens WhatsApp Web/Desktop/mobile browser depending on the user's system.
It does not confirm delivery and does not require WhatsApp Business API access.


Files likely needing changes
----------------------------
1. pages/fee_notices_dialog.py
   - Add "Open WhatsApp" button.
   - Build WhatsApp text from selected notice.
   - Validate selected notice has a usable mobile number.
   - Open the generated wa.me URL in the default browser.

2. database/database.py
   - Probably no schema changes needed for click-to-chat.
   - Optional helper can be added only if URL/message construction becomes shared.

3. dialogs/dialogs.py
   - No expected changes.

4. Optional new helper file:
   - whatsapp_utils.py
   - Use only if formatting/validation grows beyond a few local functions.


Business rules
--------------
1. Only one selected notice is acted on at a time.
2. Mobile number must be normalized before building the URL:
   - Strip spaces, hyphens, parentheses, and leading plus signs.
   - Accept 10-digit Indian numbers and prefix `91`.
   - Accept 12-digit numbers starting with `91`.
   - Reject anything else with a clear UI error.
3. Message text should include:
   - Student name
   - Seat number
   - Due date
   - Due amount
   - Existing notice message
4. Do not mark a notice as sent, paid, or cancelled just because WhatsApp opens.
5. Do not auto-send messages. User must manually send in WhatsApp.
6. Keep copy-to-clipboard available as a fallback.


Detailed implementation plan
----------------------------

Phase 1: Click-to-chat URL integration
--------------------------------------
1. Add imports in `pages/fee_notices_dialog.py`:
   - `import webbrowser`
   - `from urllib.parse import quote`

2. Add helper methods to `FeeNoticesDialog`:
   - `_normalize_whatsapp_mobile(mobile_number)`
   - `_build_whatsapp_text(row)`
   - `_build_whatsapp_url(row)`
   - `_open_whatsapp()`

3. Add UI button in the Notice Center footer:
   - Label: "Open WhatsApp"
   - Suggested color: `COLORS["success"]`
   - Place near "Copy WhatsApp Text".

4. `_open_whatsapp()` behavior:
   - Require a selected notice.
   - Validate/normalize mobile number.
   - Build message.
   - URL-encode message.
   - Call `webbrowser.open(url)`.
   - Show an error dialog if mobile number is invalid.

5. Keep the existing "Copy WhatsApp Text" button unchanged.

Phase 1 progress
----------------
- [x] Added WhatsApp URL imports in `pages/fee_notices_dialog.py`.
- [x] Added mobile normalization for Indian 10-digit and `91`-prefixed numbers.
- [x] Added WhatsApp message and URL builder helpers.
- [x] Added "Open WhatsApp" button in the Notice Center footer.
- [x] Kept notice status unchanged when opening WhatsApp.


Phase 2: Message consistency cleanup
------------------------------------
1. Reuse `_build_whatsapp_text(row)` inside both:
   - `_copy_whatsapp_text()`
   - `_open_whatsapp()`

2. Ensure the copied WhatsApp text and opened WhatsApp text match exactly.

Phase 2 progress
----------------
- [x] `_copy_whatsapp_text()` uses `_build_whatsapp_text(row)`.
- [x] `_open_whatsapp()` uses `_build_whatsapp_url(row)`, which URL-encodes `_build_whatsapp_text(row)`.
- [x] Clipboard WhatsApp text and opened WhatsApp prefill text use the same source formatter.


Phase 3: Optional status tracking
---------------------------------
Only implement later if explicitly requested.

Possible additions:
1. Add `whatsapp_opened_at TEXT` to `fee_notices`.
2. Add `mark_notice_whatsapp_opened(notice_id)` in database.
3. Show "WhatsApp Opened" timestamp in Notice Center.

Important: opening WhatsApp is not proof that the message was sent or delivered.
Avoid labels like "Sent" unless using WhatsApp Business API callbacks.


Phase 4: Optional WhatsApp Business API
---------------------------------------
Do not implement unless explicitly requested and credentials are provided.

Would require:
1. WhatsApp Business account.
2. Meta app configuration.
3. Permanent access token or secure token refresh strategy.
4. Approved message templates for outbound notifications.
5. Delivery status webhooks.
6. Secure credential storage.

This is much heavier than click-to-chat and should not be mixed into the
desktop app without a clear deployment plan.


Verification plan
-----------------
Run:

    python -m compileall -q .

Manual checks:
1. Open app.
2. Go to Fees.
3. Open Fee Notices.
4. Select a notice with a valid 10-digit mobile number.
5. Click "Open WhatsApp".
6. Confirm browser opens a `wa.me/91...` URL with prefilled text.
7. Try an invalid mobile number and confirm a clear error is shown.
8. Confirm notice status does not change just by opening WhatsApp.


Safety notes
------------
- Do not auto-send WhatsApp messages.
- Do not store API credentials in source code.
- Do not mark notices as sent without real delivery confirmation.
- URL encoding must be used for message text.
"""
