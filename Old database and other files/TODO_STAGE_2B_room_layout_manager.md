# TODO - Stage 2B Room Layout Manager

## Step 1: Database layer
- [ ] Add `room_layouts` table (with seat_spacing default 8).
- [x] Add DB methods:
  - [x] `get_room_layout(room)` returns (rows, columns, seat_spacing) with defaults (5,5,8).
  - [x] `set_room_layout(room, rows, columns, seat_spacing)`.


## Step 2: Dialog UI
- [ ] Add `RoomLayoutDialog` in `dialogs/dialogs.py`.
- [ ] Include fields: Room (A/B/C), Rows (1..50), Columns (1..50), Seat Spacing (0..100).
- [ ] Capacity preview in dialog:
  - [ ] Show seats count in selected room.
  - [ ] Show capacity = rows * columns.
- [ ] Validation + capacity error message:
  - [ ] Reject invalid ranges.
  - [ ] If capacity < seat_count_in_room show: "Layout capacity is smaller than the number of seats in this room." and do not save.

## Step 3: RoomsPage rendering + UI
- [ ] Add [Layout] button on far right of Rooms page header.
- [ ] On Layout click, open dialog with current selected room.
- [ ] Cache layout data during refresh only.
- [ ] Update rendering grid placement using cached (rows, columns, seat_spacing).
- [ ] Ensure no DB calls occur during hover/click/render (only during refresh).

## Step 4: Backward compatibility
- [ ] Ensure defaults apply if `room_layouts` missing or no row exists for a room.

## Step 5: Verification
- [ ] Run:
  - python -m py_compile database/database.py
  - python -m py_compile dialogs/dialogs.py
  - python -m py_compile pages/rooms_page.py
  - python library_assistant.py

