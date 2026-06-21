# TODO: Stage — Shift/Seat UI improvements

## Goal
Make Add Student dialog simpler (choose shift before seat) and improve Seats tab with “Half occupied” and “Doubly occupied”.

## Steps
1. Update `dialogs/dialogs.py` (`StudentDialog`)
   - Move Shift Type combobox above Seat Number.
   - Keep Seat combobox disabled/empty until shift is selected.
   - On shift selection, populate compatible seats using `db.get_compatible_seats(target_shift)`.

2. Update `pages/seats_page.py` (`SeatsPage.refresh`)
   - Stop relying only on `seats.status`.
   - Compute seat display status from active students on that seat:
     - FULL_DAY present => Occupied (red)
     - HALF_DAY_DAY only => Half Occ (day) (light grey)
     - HALF_DAY_NIGHT only => Half Occ (night) (light grey)
     - Both HALF_DAY_DAY + HALF_DAY_NIGHT => Doubly occupied (blue) label
   - Update tree tag_configure to add the new light grey and blue tags.

3. Run `python -m compileall ...` to ensure syntax correctness.

4. Run the app and manually verify:
   - Add Student flow: shift dropdown first; seat list appears after shift selection.
   - Seats tab: correct labels/colors for Available / Occupied / Half Occ (day) / Half Occ (night) / Doubly occupied.

