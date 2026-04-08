"""
database.py — All PostgreSQL database operations.
CHANGES:
  - documents table: added file_type TEXT and mime_type TEXT columns
  - save_document_to_db: accepts file_bytes, file_type, mime_type (pdf_bytes kept for compat)
  - get_document_file_info(pg_url, filename) → (bytes, file_type, mime_type)
  - has_file_blob() added (generic); has_pdf_blob() kept as backward-compat alias
  - All migrations run safely on existing databases
"""

import hashlib
import pickle
import time
from typing import List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras
import streamlit as st
from psycopg2 import DatabaseError, OperationalError

from config import SEED_USERS


# ─────────────────────────────────────────────
# PASSWORD VALIDATION
# ─────────────────────────────────────────────
def validate_password(password: str) -> Tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number (0-9)."
    special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character (e.g. !@#$%^&*)."
    return True, "OK"


# ─────────────────────────────────────────────
# CONNECTION
# ─────────────────────────────────────────────
def get_db_connection(pg_url: str):
    try:
        conn = psycopg2.connect(pg_url, connect_timeout=10)
        return conn
    except OperationalError as e:
        print(f"[DB] Connection failed: {e}")
        return None
    except Exception as e:
        print(f"[DB] Unexpected connection error: {e}")
        return None


# ─────────────────────────────────────────────
# MIME TYPE HELPER
# ─────────────────────────────────────────────
_MIME_MAP = {
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc":  "application/msword",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls":  "application/vnd.ms-excel",
    "csv":  "text/csv",
    "txt":  "text/plain",
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
}

def mime_for_ext(ext: str) -> str:
    """Return MIME type string for a file extension (without dot), e.g. 'pdf' → 'application/pdf'."""
    return _MIME_MAP.get(ext.lower().lstrip("."), "application/octet-stream")

def ext_from_filename(filename: str) -> str:
    """Return lowercase extension without dot, e.g. 'report.PDF' → 'pdf'."""
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return ""


# ─────────────────────────────────────────────
# INIT — create all tables & seed users
# ─────────────────────────────────────────────
def init_db(pg_url: str) -> bool:
    conn = get_db_connection(pg_url)
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin','staff','student')),
                    display_name TEXT NOT NULL,
                    email TEXT,
                    language TEXT DEFAULT 'en',
                    onboarded BOOLEAN DEFAULT FALSE,
                    last_active TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            migrations = [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en'",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarded BOOLEAN DEFAULT FALSE",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active TIMESTAMP DEFAULT NOW()",
                "UPDATE users SET onboarded=TRUE WHERE onboarded IS NULL",
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'General'",
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS pdf_blob BYTEA",
                # New columns for generic file storage
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_type TEXT DEFAULT 'pdf'",
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS mime_type TEXT DEFAULT 'application/pdf'",
                "ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en'",
                "ALTER TABLE query_log ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en'",
            ]
            for m in migrations:
                try:
                    cur.execute(m)
                    conn.commit()
                except Exception:
                    conn.rollback()

            cur.execute("SELECT COUNT(*) FROM users")
            if cur.fetchone()[0] == 0:
                for uname, phash, role, display in SEED_USERS:
                    cur.execute("""
                        INSERT INTO users (username, password_hash, role, display_name, onboarded)
                        VALUES (%s,%s,%s,%s,TRUE) ON CONFLICT (username) DO NOTHING
                    """, (uname, phash, role, display))

            cur.execute("""
                CREATE TABLE IF NOT EXISTS doc_categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    color TEXT DEFAULT '#00c9a7'
                );
            """)
            cur.execute("SELECT COUNT(*) FROM doc_categories")
            if cur.fetchone()[0] == 0:
                for cat in [("Exam","#f05252"),("Admission","#4f8ef7"),
                            ("Rules","#f0a500"),("Timetable","#0ea472"),("General","#8b92a9")]:
                    cur.execute("INSERT INTO doc_categories (name,color) VALUES (%s,%s) ON CONFLICT DO NOTHING", cat)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    uploaded_by TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT NOW(),
                    chunk_count INTEGER,
                    chunks_blob BYTEA,
                    embeddings_blob BYTEA,
                    used_ocr BOOLEAN DEFAULT FALSE,
                    category TEXT DEFAULT 'General',
                    pdf_blob BYTEA,
                    file_type TEXT DEFAULT 'pdf',
                    mime_type TEXT DEFAULT 'application/pdf'
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources TEXT,
                    confidence FLOAT,
                    language TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS query_log (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    query TEXT,
                    response_time_ms INTEGER,
                    confidence FLOAT,
                    success BOOLEAN,
                    language TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    rating INTEGER NOT NULL CHECK (rating IN (1,-1)),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    request_count INTEGER DEFAULT 1,
                    window_start TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    message TEXT NOT NULL,
                    type TEXT DEFAULT 'info',
                    read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()
        return True
    except DatabaseError as e:
        print(f"[DB] init_db error: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


# ─────────────────────────────────────────────
# USER MANAGEMENT
# ─────────────────────────────────────────────
def db_authenticate(pg_url: str, username: str, password: str) -> Optional[dict]:
    conn = get_db_connection(pg_url)
    if not conn:
        return None
    try:
        phash = hashlib.sha256(password.encode()).hexdigest()
        uname = username.strip().lower()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT username,role,display_name FROM users WHERE LOWER(username)=%s AND password_hash=%s",
                (uname, phash)
            )
            row = cur.fetchone()
            if row:
                email, language, onboarded = None, "en", True
                try:
                    cur.execute("SELECT email,language,onboarded FROM users WHERE username=%s", (row["username"],))
                    extra = cur.fetchone()
                    if extra:
                        email     = extra["email"]
                        language  = extra["language"] or "en"
                        onboarded = extra["onboarded"] if extra["onboarded"] is not None else True
                except Exception:
                    pass
                try:
                    cur.execute("UPDATE users SET last_active=NOW() WHERE username=%s", (row["username"],))
                    conn.commit()
                except Exception:
                    pass
                return {"username":row["username"],"role":row["role"],"display":row["display_name"],
                        "email":email,"language":language,"onboarded":onboarded}
        return None
    except DatabaseError:
        return None
    finally:
        conn.close()


def get_all_users(pg_url: str) -> list:
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id,username,role,display_name,email,last_active,created_at FROM users ORDER BY created_at")
            return cur.fetchall()
    except DatabaseError:
        return []
    finally:
        conn.close()


def add_user(pg_url: str, username: str, password: str, role: str,
             display_name: str, email: str = "") -> Tuple[bool, str]:
    if not username or not password or not display_name:
        return False, "All fields are required."
    if not email or not email.strip():
        return False, "Email is required."
    if role not in ("admin","staff","student"):
        return False, "Invalid role."
    ok, msg = validate_password(password)
    if not ok:
        return False, msg
    conn = get_db_connection(pg_url)
    if not conn:
        return False, "Database connection failed."
    try:
        phash = hashlib.sha256(password.encode()).hexdigest()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username,password_hash,role,display_name,email,onboarded) VALUES (%s,%s,%s,%s,%s,FALSE)",
                (username.strip().lower(), phash, role, display_name.strip(), email.strip())
            )
        conn.commit()
        add_notification(pg_url, username.strip().lower(),
                         f"Welcome to College AI Assistant, {display_name}!", "success")
        return True, "User created successfully."
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, f"Username '{username}' already exists."
    except DatabaseError as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def delete_user(pg_url: str, user_id: int, current_username: str) -> Tuple[bool, str]:
    conn = get_db_connection(pg_url)
    if not conn:
        return False, "Database connection failed."
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM users WHERE id=%s", (user_id,))
            row = cur.fetchone()
            if not row:
                return False, "User not found."
            if row[0] == current_username:
                return False, "You cannot delete your own account."
            cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()
        return True, "User deleted."
    except DatabaseError as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def change_password(pg_url: str, username: str, old_password: str,
                    new_password: str) -> Tuple[bool, str]:
    ok, msg = validate_password(new_password)
    if not ok:
        return False, msg
    conn = get_db_connection(pg_url)
    if not conn:
        return False, "Database connection failed."
    try:
        old_hash = hashlib.sha256(old_password.encode()).hexdigest()
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s AND password_hash=%s", (username, old_hash))
            if not cur.fetchone():
                return False, "Current password is incorrect."
            cur.execute("UPDATE users SET password_hash=%s WHERE username=%s", (new_hash, username))
        conn.commit()
        return True, "Password changed successfully."
    except DatabaseError as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def update_user_language(pg_url: str, username: str, language: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET language=%s WHERE username=%s", (language, username))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


def mark_onboarded(pg_url: str, username: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET onboarded=TRUE WHERE username=%s", (username,))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


def update_last_active(pg_url: str, username: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET last_active=NOW() WHERE username=%s", (username,))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


# ─────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────
def save_document_to_db(pg_url: str, filename: str, username: str,
                        chunks: List[str], embeddings: np.ndarray,
                        used_ocr: bool = False, category: str = "General",
                        pdf_bytes: Optional[bytes] = None,       # kept for backward compat
                        file_bytes: Optional[bytes] = None,      # preferred going forward
                        file_type: str = "pdf",
                        mime_type: str = "application/pdf") -> bool:
    """
    Save a document to the database.

    Pass file_bytes + file_type + mime_type for non-PDF uploads.
    pdf_bytes is accepted for backward compatibility and treated as file_bytes when file_bytes is None.
    """
    conn = get_db_connection(pg_url)
    if not conn:
        return False
    try:
        # Prefer file_bytes; fall back to pdf_bytes for old callers
        actual_bytes = file_bytes if file_bytes is not None else pdf_bytes

        chunks_blob     = pickle.dumps(chunks)
        embeddings_blob = pickle.dumps(embeddings)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE filename=%s", (filename,))
            cur.execute("""
                INSERT INTO documents
                    (filename, uploaded_by, chunk_count, chunks_blob, embeddings_blob,
                     used_ocr, category, pdf_blob, file_type, mime_type)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                filename, username, len(chunks),
                psycopg2.Binary(chunks_blob), psycopg2.Binary(embeddings_blob),
                used_ocr, category,
                psycopg2.Binary(actual_bytes) if actual_bytes else None,
                file_type, mime_type,
            ))
        conn.commit()
        _notify_all_students(pg_url, f"New document uploaded: {filename} ({category})")
        return True
    except DatabaseError as e:
        print(f"[DB] Failed to save document '{filename}': {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def _notify_all_students(pg_url: str, message: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM users WHERE role='student'")
            for row in cur.fetchall():
                cur.execute(
                    "INSERT INTO notifications (username,message,type) VALUES (%s,%s,'info')",
                    (row[0], message)
                )
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


def has_file_blob(pg_url: str, filename: str) -> bool:
    """Return True if this document has stored original file bytes ready for download."""
    conn = get_db_connection(pg_url)
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pdf_blob IS NOT NULL AND octet_length(pdf_blob) > 0 "
                "FROM documents WHERE filename=%s",
                (filename,)
            )
            row = cur.fetchone()
            return bool(row and row[0])
    except DatabaseError:
        return False
    finally:
        conn.close()


# Backward-compat alias
has_pdf_blob = has_file_blob


def get_document_bytes(pg_url: str, filename: str) -> Optional[bytes]:
    """Retrieve the raw file bytes for a given document filename."""
    conn = get_db_connection(pg_url)
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pdf_blob FROM documents WHERE filename=%s", (filename,))
            row = cur.fetchone()
            if row and row[0]:
                raw = row[0]
                return bytes(raw) if not isinstance(raw, bytes) else raw
        return None
    except DatabaseError as e:
        print(f"[DB] get_document_bytes error for '{filename}': {e}")
        return None
    finally:
        conn.close()


def get_document_file_info(pg_url: str, filename: str) -> Tuple[Optional[bytes], str, str]:
    """
    Retrieve the raw file bytes plus file_type and mime_type for a document.

    Returns (bytes, file_type, mime_type).
    Returns (None, 'pdf', 'application/pdf') if not found or on error.
    """
    conn = get_db_connection(pg_url)
    if not conn:
        return None, "pdf", "application/pdf"
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pdf_blob, file_type, mime_type FROM documents WHERE filename=%s",
                (filename,)
            )
            row = cur.fetchone()
            if row:
                raw, ftype, fmime = row
                data = (bytes(raw) if raw and not isinstance(raw, bytes) else raw) if raw else None
                return data, (ftype or "pdf"), (fmime or "application/pdf")
        return None, "pdf", "application/pdf"
    except DatabaseError as e:
        print(f"[DB] get_document_file_info error for '{filename}': {e}")
        return None, "pdf", "application/pdf"
    finally:
        conn.close()


def load_all_documents_from_db(pg_url: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return None, [], [], []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT filename,chunk_count,chunks_blob,embeddings_blob,used_ocr,category FROM documents ORDER BY uploaded_at")
            rows = cur.fetchall()
        if not rows:
            return None, [], [], []
        all_chunks, all_embeddings, doc_list, chunk_doc_names = [], [], [], []
        for row in rows:
            try:
                chunks     = pickle.loads(bytes(row['chunks_blob']))
                embeddings = pickle.loads(bytes(row['embeddings_blob']))
                all_chunks.extend(chunks)
                for _ in chunks:
                    chunk_doc_names.append(row['filename'])
                all_embeddings.append(embeddings)
                doc_list.append({
                    "filename": row['filename'],
                    "chunks":   row['chunk_count'],
                    "used_ocr": row['used_ocr'],
                    "category": row['category'] or 'General'
                })
            except Exception as e:
                print(f"[DB] Skipping corrupt document row: {e}")
                continue
        if not all_embeddings:
            return None, [], doc_list, chunk_doc_names
        return np.vstack(all_embeddings), all_chunks, doc_list, chunk_doc_names
    except Exception as e:
        print(f"[DB] load_all_documents_from_db error: {e}")
        return None, [], [], []
    finally:
        conn.close()


def get_document_list(pg_url: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id,filename,uploaded_by,uploaded_at,chunk_count,used_ocr,category FROM documents ORDER BY uploaded_at DESC")
            return cur.fetchall()
    except DatabaseError:
        return []
    finally:
        conn.close()


def delete_document(pg_url: str, doc_id: int) -> bool:
    conn = get_db_connection(pg_url)
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
        conn.commit()
        return True
    except DatabaseError as e:
        print(f"[DB] Delete document failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_categories(pg_url: str) -> list:
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT name,color FROM doc_categories ORDER BY name")
            return cur.fetchall()
    except DatabaseError:
        return []
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CHAT HISTORY
# ─────────────────────────────────────────────
def save_chat_message(pg_url: str, username: str, role: str, content: str,
                      sources: Optional[str] = None, confidence: Optional[float] = None,
                      language: str = "en"):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_history (username,role,content,sources,confidence,language)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (username, role, content, sources, confidence, language))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


def load_chat_history(pg_url: str, username: str, limit: int = 50):
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT role,content,sources,confidence,created_at
                FROM chat_history WHERE username=%s
                ORDER BY created_at DESC LIMIT %s
            """, (username, limit))
            return list(reversed(cur.fetchall()))
    except DatabaseError:
        return []
    finally:
        conn.close()


def clear_chat_history(pg_url: str, username: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_history WHERE username=%s", (username,))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


# ─────────────────────────────────────────────
# QUERY LOG & STATS
# ─────────────────────────────────────────────
def log_query(pg_url: str, username: str, query: str,
              response_time_ms: int, confidence: float, success: bool, language: str = "en"):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO query_log (username,query,response_time_ms,confidence,success,language)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (username, query, response_time_ms, confidence, success, language))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


def get_stats(pg_url: str) -> dict:
    conn = get_db_connection(pg_url)
    if not conn:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents");            docs      = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM query_log");            queries   = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(chunk_count),0) FROM documents"); chunks = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(AVG(confidence),0) FROM query_log WHERE confidence IS NOT NULL"); avg_c = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM users");                users     = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM feedback");             feedback  = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM feedback WHERE rating=1"); thumbs_up = cur.fetchone()[0]
        return {"docs":docs,"queries":queries,"chunks":chunks,
                "avg_conf":round(float(avg_c)*100, 1),"users":users,
                "feedback":feedback,"thumbs_up":thumbs_up}
    except DatabaseError:
        return {}
    finally:
        conn.close()


def get_queries_per_day(pg_url: str, days: int = 7) -> list:
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT DATE(created_at) as day, COUNT(*) as count
                FROM query_log
                WHERE created_at >= NOW() - INTERVAL '%s days'
                GROUP BY DATE(created_at)
                ORDER BY day
            """, (days,))
            return cur.fetchall()
    except DatabaseError:
        return []
    finally:
        conn.close()


def get_top_queries(pg_url: str, limit: int = 10) -> list:
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT query, COUNT(*) as count
                FROM query_log
                GROUP BY query
                ORDER BY count DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
    except DatabaseError:
        return []
    finally:
        conn.close()


def get_avg_response_time(pg_url: str) -> float:
    conn = get_db_connection(pg_url)
    if not conn:
        return 0.0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(AVG(response_time_ms),0) FROM query_log WHERE success=TRUE")
            result = cur.fetchone()[0]
            return round(float(result), 1)
    except DatabaseError:
        return 0.0
    finally:
        conn.close()


def get_active_users_today(pg_url: str) -> int:
    conn = get_db_connection(pg_url)
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT username) FROM query_log WHERE created_at >= CURRENT_DATE")
            return cur.fetchone()[0]
    except DatabaseError:
        return 0
    finally:
        conn.close()


# ─────────────────────────────────────────────
# FEEDBACK
# ─────────────────────────────────────────────
def save_feedback(pg_url: str, username: str, query: str,
                  answer: str, rating: int) -> bool:
    conn = get_db_connection(pg_url)
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO feedback (username,query,answer,rating)
                VALUES (%s,%s,%s,%s)
            """, (username, query, answer, rating))
        conn.commit()
        return True
    except DatabaseError:
        return False
    finally:
        conn.close()


def get_feedback_list(pg_url: str, limit: int = 20) -> list:
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT username,query,rating,created_at
                FROM feedback ORDER BY created_at DESC LIMIT %s
            """, (limit,))
            return cur.fetchall()
    except DatabaseError:
        return []
    finally:
        conn.close()


# ─────────────────────────────────────────────
# RATE LIMITING
# ─────────────────────────────────────────────
def check_rate_limit(pg_url: str, username: str, max_per_hour: int = 30) -> Tuple[bool, int]:
    conn = get_db_connection(pg_url)
    if not conn:
        return True, max_per_hour
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, request_count, window_start
                FROM rate_limit WHERE username=%s
                ORDER BY window_start DESC LIMIT 1
            """, (username,))
            row = cur.fetchone()
            now = time.time()
            if row:
                rid, count, window_start = row
                window_age = (now - window_start.timestamp())
                if window_age < 3600:
                    if count >= max_per_hour:
                        return False, 0
                    cur.execute("UPDATE rate_limit SET request_count=%s WHERE id=%s", (count+1, rid))
                    conn.commit()
                    return True, max_per_hour - count - 1
                else:
                    cur.execute("UPDATE rate_limit SET request_count=1,window_start=NOW() WHERE id=%s", (rid,))
                    conn.commit()
                    return True, max_per_hour - 1
            else:
                cur.execute("INSERT INTO rate_limit (username) VALUES (%s)", (username,))
                conn.commit()
                return True, max_per_hour - 1
    except DatabaseError:
        return True, max_per_hour
    finally:
        conn.close()


# ─────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────
def add_notification(pg_url: str, username: str, message: str, type_: str = "info"):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO notifications (username,message,type) VALUES (%s,%s,%s)",
                (username, message, type_)
            )
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


def get_notifications(pg_url: str, username: str) -> list:
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT id,message,type,read,created_at
                FROM notifications WHERE username=%s
                ORDER BY created_at DESC LIMIT 10
            """, (username,))
            return cur.fetchall()
    except DatabaseError:
        return []
    finally:
        conn.close()


def mark_notifications_read(pg_url: str, username: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE notifications SET read=TRUE WHERE username=%s", (username,))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


def get_unread_count(pg_url: str, username: str) -> int:
    conn = get_db_connection(pg_url)
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM notifications WHERE username=%s AND read=FALSE", (username,))
            return cur.fetchone()[0]
    except DatabaseError:
        return 0
    finally:
        conn.close()