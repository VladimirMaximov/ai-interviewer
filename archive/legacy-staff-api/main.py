from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import hashlib
import uuid
try:
    from .database import get_db, init_db
except ImportError:
    from database import get_db, init_db

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

# Модели
class User(BaseModel):
    username: str
    password: str

class VacancyCreate(BaseModel):
    title: str
    description: str
    recruiter_id: str
    manager_id: str
    questions: List[str] = []

class VacancyUpdate(BaseModel):
    title: str
    description: str
    questions: List[str] = []

# Пользователи
@app.post("/api/register")
async def register(user: User, role: str = "candidate", full_name: str = ""):
    with get_db() as conn:
        if conn.execute("SELECT * FROM users WHERE username = ?", (user.username,)).fetchone():
            raise HTTPException(400, "Пользователь уже существует")
        
        uid = str(uuid.uuid4())[:8]
        pwd_hash = hashlib.sha256(user.password.encode()).hexdigest()
        conn.execute(
            "INSERT INTO users (id, username, password, role, full_name) VALUES (?, ?, ?, ?, ?)",
            (uid, user.username, pwd_hash, role, full_name or user.username)
        )
    return {"id": uid, "username": user.username, "role": role}

@app.post("/api/login")
async def login(user: User):
    with get_db() as conn:
        pwd_hash = hashlib.sha256(user.password.encode()).hexdigest()
        result = conn.execute(
            "SELECT id, username, role FROM users WHERE username=? AND password=?",
            (user.username, pwd_hash)
        ).fetchone()
        if not result:
            raise HTTPException(401, "Неверный логин или пароль")
        return {"id": result["id"], "username": result["username"], "role": result["role"]}

# Вакансии
@app.get("/api/vacancies")
async def get_vacancies():
    with get_db() as conn:
        vacancies = conn.execute("""
            SELECT v.*, 
                   (SELECT COUNT(*) FROM questions WHERE vacancy_id = v.id) as questions_count
            FROM vacancies v WHERE v.status = 'active'
            ORDER BY v.created_at DESC, v.rowid DESC
        """).fetchall()
        return [dict(row) for row in vacancies]

@app.get("/api/vacancies/{vacancy_id}")
async def get_vacancy(vacancy_id: str):
    with get_db() as conn:
        vacancy = conn.execute("SELECT * FROM vacancies WHERE id = ?", (vacancy_id,)).fetchone()
        if not vacancy:
            raise HTTPException(404, "Вакансия не найдена")
        questions = conn.execute(
            "SELECT * FROM questions WHERE vacancy_id = ? ORDER BY order_num",
            (vacancy_id,)
        ).fetchall()
        result = dict(vacancy)
        result["questions"] = [dict(q) for q in questions]
        return result

@app.post("/api/vacancies")
async def create_vacancy(vacancy: VacancyCreate):
    vid = str(uuid.uuid4())[:8]
    with get_db() as conn:
        conn.execute(
            "INSERT INTO vacancies (id, title, description, recruiter_id, manager_id) VALUES (?, ?, ?, ?, ?)",
            (vid, vacancy.title, vacancy.description, vacancy.recruiter_id, vacancy.manager_id)
        )
        for i, q in enumerate(vacancy.questions):
            if q.strip():
                conn.execute(
                    "INSERT INTO questions (id, vacancy_id, question_text, order_num) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4())[:8], vid, q.strip(), i)
                )
    return {
        "id": vid,
        "title": vacancy.title,
        "description": vacancy.description,
        "recruiter_id": vacancy.recruiter_id,
        "manager_id": vacancy.manager_id,
        "questions": [question.strip() for question in vacancy.questions if question.strip()],
        "status": "active",
        "success": True,
    }

@app.put("/api/vacancies/{vacancy_id}")
async def update_vacancy(vacancy_id: str, vacancy: VacancyUpdate):
    with get_db() as conn:
        conn.execute(
            "UPDATE vacancies SET title = ?, description = ? WHERE id = ?",
            (vacancy.title, vacancy.description, vacancy_id)
        )
        conn.execute("DELETE FROM questions WHERE vacancy_id = ?", (vacancy_id,))
        for i, q in enumerate(vacancy.questions):
            if q.strip():
                conn.execute(
                    "INSERT INTO questions (id, vacancy_id, question_text, order_num) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4())[:8], vacancy_id, q.strip(), i)
                )
    return {"success": True}

# Лидерборд
@app.get("/api/leaderboard/{vacancy_id}")
async def get_leaderboard(vacancy_id: str):
    with get_db() as conn:
        results = conn.execute("""
            SELECT l.*, u.full_name as name
            FROM leaderboard l
            JOIN users u ON l.candidate_id = u.id
            WHERE l.vacancy_id = ?
            ORDER BY l.score DESC
        """, (vacancy_id,)).fetchall()
        return [dict(row) for row in results]

@app.post("/api/leaderboard")
async def add_leaderboard(
    vacancy_id: str,
    candidate_id: str,
    score: int,
    recruiter_score: Optional[int] = None,
    manager_score: Optional[int] = None,
    comment: Optional[str] = None,
    date: Optional[str] = None
):
    lid = str(uuid.uuid4())[:8]
    with get_db() as conn:
        conn.execute("""
            INSERT INTO leaderboard (id, vacancy_id, candidate_id, score, recruiter_score, manager_score, comment, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (lid, vacancy_id, candidate_id, score, recruiter_score, manager_score, comment, date))
    return {"success": True, "id": lid}

@app.put("/api/leaderboard/{leaderboard_id}")
async def update_leaderboard(leaderboard_id: str, recruiter_score: int = None, manager_score: int = None):
    with get_db() as conn:
        if recruiter_score is not None:
            conn.execute("UPDATE leaderboard SET recruiter_score = ? WHERE id = ?", (recruiter_score, leaderboard_id))
        if manager_score is not None:
            conn.execute("UPDATE leaderboard SET manager_score = ? WHERE id = ?", (manager_score, leaderboard_id))
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
