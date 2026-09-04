# main.py
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, hashlib, uuid
from contextlib import contextmanager

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@contextmanager
def db():
    conn = sqlite3.connect("interview.db")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.commit()
    conn.close()

def init():
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id TEXT, username TEXT, password TEXT, role TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS vacancies (id TEXT, title TEXT, desc TEXT, author_id TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS questions (id TEXT, vacancy_id TEXT, text TEXT)")
        
        if not conn.execute("SELECT * FROM users").fetchone():
            pwd = hashlib.sha256("1234".encode()).hexdigest()
            conn.execute("INSERT INTO users VALUES ('1', 'interviewer', ?, 'interviewer')", (pwd,))
            conn.execute("INSERT INTO users VALUES ('2', 'candidate', ?, 'candidate')", (pwd,))
            conn.execute("INSERT INTO users VALUES ('3', 'manager', ?, 'hiring_manager')", (pwd,))
            
            conn.execute("INSERT INTO vacancies VALUES ('1', 'Middle Python разработчик', 'Разработка бэкенда на Python', '1')")
            conn.execute("INSERT INTO vacancies VALUES ('2', 'Junior Data Scientist', 'Анализ данных и ML', '1')")
            
            conn.execute("INSERT INTO questions VALUES ('q1', '1', 'Расскажите о опыте работы с Django')")
            conn.execute("INSERT INTO questions VALUES ('q2', '1', 'Как тестируете код?')")
init()

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", 
                           (username, hash_pwd(password))).fetchone()
    if not user:
        raise HTTPException(401, "Неверный логин или пароль")
    return {"id": user["id"], "username": user["username"], "role": user["role"]}

@app.get("/api/vacancies")
async def get_vacancies():
    with db() as conn:
        return [dict(v) for v in conn.execute("SELECT * FROM vacancies").fetchall()]

@app.get("/api/vacancies/{vacancy_id}")
async def get_vacancy(vacancy_id: str):
    with db() as conn:
        vac = conn.execute("SELECT * FROM vacancies WHERE id=?", (vacancy_id,)).fetchone()
        if not vac:
            raise HTTPException(404, "Вакансия не найдена")
        questions = conn.execute("SELECT * FROM questions WHERE vacancy_id=?", (vacancy_id,)).fetchall()
    return {**dict(vac), "questions": [dict(q) for q in questions]}

@app.post("/api/vacancies")
async def create_vacancy(title: str = Form(...), desc: str = Form(...), author_id: str = Form(...)):
    vid = str(uuid.uuid4())[:8]
    with db() as conn:
        conn.execute("INSERT INTO vacancies VALUES (?, ?, ?, ?)", (vid, title, desc, author_id))
    return {"id": vid}

@app.put("/api/vacancies/{vacancy_id}")
async def update_vacancy(vacancy_id: str, title: str = Form(...), desc: str = Form(...), questions: list = Form([])):
    with db() as conn:
        conn.execute("UPDATE vacancies SET title=?, desc=? WHERE id=?", (title, desc, vacancy_id))
        conn.execute("DELETE FROM questions WHERE vacancy_id=?", (vacancy_id,))
        for q in questions:
            if q.strip():
                conn.execute("INSERT INTO questions VALUES (?, ?, ?)", (str(uuid.uuid4())[:8], vacancy_id, q.strip()))
    return {"success": True}

@app.get("/api/leaderboard")
async def get_leaderboard():
    return [
        {"name": "Анна С.", "score": 92},
        {"name": "Михаил К.", "score": 87},
        {"name": "Екатерина П.", "score": 81},
    ]