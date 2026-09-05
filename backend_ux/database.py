import sqlite3
import hashlib
from contextlib import contextmanager
from pathlib import Path

DATABASE_URL = Path(__file__).resolve().with_name("interview.db")

DEFAULT_USERS = (
    ("1", "interviewer", "interviewer", "Interviewer"),
    ("2", "candidate", "candidate", "Candidate"),
    ("3", "manager", "hiring_manager", "Hiring Manager"),
)

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.commit()
    conn.close()

def init_db():
    with get_db() as conn:
        # Таблица пользователей
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица вакансий
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vacancies (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                recruiter_id TEXT,
                manager_id TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recruiter_id) REFERENCES users (id),
                FOREIGN KEY (manager_id) REFERENCES users (id)
            )
        """)

        # Таблица вопросов
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                vacancy_id TEXT NOT NULL,
                question_text TEXT NOT NULL,
                order_num INTEGER DEFAULT 0,
                FOREIGN KEY (vacancy_id) REFERENCES vacancies (id) ON DELETE CASCADE
            )
        """)

        # Таблица лидерборда
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                id TEXT PRIMARY KEY,
                vacancy_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                score INTEGER DEFAULT 0,
                recruiter_score INTEGER,
                manager_score INTEGER,
                comment TEXT,
                transcript TEXT,
                date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vacancy_id) REFERENCES vacancies (id) ON DELETE CASCADE,
                FOREIGN KEY (candidate_id) REFERENCES users (id)
            )
        """)

        default_password = hashlib.sha256("1234".encode("utf-8")).hexdigest()
        conn.executemany(
            """
            INSERT OR IGNORE INTO users
                (id, username, password, role, full_name)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (user_id, username, default_password, role, full_name)
                for user_id, username, role, full_name in DEFAULT_USERS
            ],
        )
