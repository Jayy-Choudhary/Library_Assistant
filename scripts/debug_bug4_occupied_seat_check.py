from database.database import Database
import sqlite3

DB_PATH = 'library_assistant.db'

db = Database(DB_PATH)
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Find one active student and the seat they occupy
row = cur.execute(
    "SELECT seat_number, shift_type FROM students WHERE status='Active' ORDER BY id LIMIT 1"
).fetchone()

print('active_student_row:', row)
seat = row[0] if row else None
shift_type = row[1] if row else None

if not seat:
    print('NO_ACTIVE_STUDENTS_FOUND')
    raise SystemExit(0)

# Check membership in compatible dropdown lists
full_day_set = set(db.get_compatible_seats('FULL_DAY'))
half_day_day_set = set(db.get_compatible_seats('HALF_DAY_DAY'))
half_day_night_set = set(db.get_compatible_seats('HALF_DAY_NIGHT'))

print('tested_seat:', seat)
print('tested_shift_type_from_db:', shift_type)

print('seat_in_FULL_DAY_compatible:', seat in full_day_set)
print('seat_in_HALF_DAY_DAY_compatible:', seat in half_day_day_set)
print('seat_in_HALF_DAY_NIGHT_compatible:', seat in half_day_night_set)

# Also print counts for sanity
print('compatible_counts:', {
    'FULL_DAY': len(full_day_set),
    'HALF_DAY_DAY': len(half_day_day_set),
    'HALF_DAY_NIGHT': len(half_day_night_set)
})

