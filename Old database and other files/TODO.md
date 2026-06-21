# TODO - Student Photo Management Feature

## Plan (approved)
1. Scan student-related code paths (add/edit/archive/export/refresh) and identify all required integration points.
2. Add `student_photos/` folder support and image processing utilities (resize + thumbnails).
3. Database migration: add nullable `photo_path` column to `students` and add DB helper methods.
4. Update `StudentDialog` UI with photo upload/remove + preview.
5. Update `StudentsPage`:
   - double-click row → read-only Student Profile dialog
   - hover preview near cursor only for Full Name cell
   - integrate photo paths + thumbnail caching.
6. Add `StudentProfileDialog` read-only implementation.
7. Ensure old student preservation (no changes on status transitions beyond status).
8. Manual testing checklist.

## Progress
- [x] 1) Scan
- [x] 2) Utilities + folder
- [x] 3) DB schema + methods
- [x] 4) Dialog upload/remove + preview
- [x] 5) Students page profile + hover
- [x] 6) Profile dialog
- [x] 7) Old student preservation
- [x] 8) Test

