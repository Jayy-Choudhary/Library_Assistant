# Web_App_Lib_Assistant

Web app wrapper for the Library Assistant (SQLite backend reused).

## Run

### 1) Create venv
```bat
cd /d d:\PYTHON\@_Projects_For_2026\Library_Assistant\Web_App_Lib_Assistant
python -m venv .venv
.
\.venv\Scripts\activate
```

### 2) Install deps
```bat
pip install -r requirements.txt
```

### 3) Start server
```bat
uvicorn main:app --reload --port 8000
```

Open:
- http://127.0.0.1:8000/

