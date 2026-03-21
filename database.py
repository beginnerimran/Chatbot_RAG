"""
database.py — All PostgreSQL database operations.
Handles: connection, init, users, documents, chat history, query logging, stats.
"""

import hashlib
import pickle
from typing import List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras
import streamlit as st
from psycopg2 import DatabaseError, OperationalError

from config import SEED_USERS


# ─────────────────────────────────────────────
# CONNECTION
# ─────────────────────────────────────────────
def get_db_connection(pg_url: str):
    try:
        conn = psycopg2.connect(pg_url, connect_timeout=10)
        return conn
    except OperationalError as e:
        st.error(f"❌ Database connection failed: {e}")
        return None


# ─────────────────────────────────────────────
# INIT — create tables & seed users
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
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("SELECT COUNT(*) FROM users")
            if cur.fetchone()[0] == 0:
                for uname, phash, role, display in SEED_USERS:
                    cur.execute("""
                        INSERT INTO users (username, password_hash, role, display_name)
                        VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING
                    """, (uname, phash, role, display))

            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    uploaded_by TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT NOW(),
                    chunk_count INTEGER,
                    chunks_blob BYTEA,
                    embeddings_blob BYTEA,
                    used_ocr BOOLEAN DEFAULT FALSE
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
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()
        return True
    except DatabaseError as e:
        st.error(f"❌ DB init error: {e}")
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
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT username, role, display_name FROM users WHERE username=%s AND password_hash=%s",
                (username.strip().lower(), phash)
            )
            row = cur.fetchone()
        if row:
            return {"username": row["username"], "role": row["role"], "display": row["display_name"]}
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
            cur.execute("SELECT id, username, role, display_name, created_at FROM users ORDER BY created_at")
            return cur.fetchall()
    except DatabaseError:
        return []
    finally:
        conn.close()


def add_user(pg_url: str, username: str, password: str, role: str, display_name: str) -> Tuple[bool, str]:
    if not username or not password or not display_name:
        return False, "All fields are required."
    if role not in ("admin", "staff", "student"):
        return False, "Invalid role."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    conn = get_db_connection(pg_url)
    if not conn:
        return False, "Database connection failed."
    try:
        phash = hashlib.sha256(password.encode()).hexdigest()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, display_name) VALUES (%s,%s,%s,%s)",
                (username.strip().lower(), phash, role, display_name.strip())
            )
        conn.commit()
        return True, "User created successfully."
    except psycopg2.errors.UniqueViolation:
        return False, f"Username '{username}' already exists."
    except DatabaseError as e:
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
        return False, str(e)
    finally:
        conn.close()


def change_password(pg_url: str, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters."
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
        return False, str(e)
    finally:
        conn.close()


# ─────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────
def save_document_to_db(pg_url: str, filename: str, username: str,
                        chunks: List[str], embeddings: np.ndarray,
                        used_ocr: bool = False) -> bool:
    conn = get_db_connection(pg_url)
    if not conn:
        return False
    try:
        chunks_blob     = pickle.dumps(chunks)
        embeddings_blob = pickle.dumps(embeddings)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE filename = %s", (filename,))
            cur.execute("""
                INSERT INTO documents (filename, uploaded_by, chunk_count, chunks_blob, embeddings_blob, used_ocr)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (filename, username, len(chunks),
                  psycopg2.Binary(chunks_blob),
                  psycopg2.Binary(embeddings_blob),
                  used_ocr))
        conn.commit()
        return True
    except DatabaseError as e:
        st.error(f"❌ Failed to save document: {e}")
        return False
    finally:
        conn.close()


def load_all_documents_from_db(pg_url: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return None, None, []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT filename, chunk_count, chunks_blob, embeddings_blob, used_ocr FROM documents ORDER BY uploaded_at")
            rows = cur.fetchall()

        if not rows:
            return None, None, []

        all_chunks, all_embeddings, doc_list = [], [], []
        for row in rows:
            chunks     = pickle.loads(bytes(row['chunks_blob']))
            embeddings = pickle.loads(bytes(row['embeddings_blob']))
            all_chunks.extend(chunks)
            all_embeddings.append(embeddings)
            doc_list.append({"filename": row['filename'], "chunks": row['chunk_count'], "used_ocr": row['used_ocr']})

        return np.vstack(all_embeddings), all_chunks, doc_list

    except Exception as e:
        st.error(f"❌ Failed to load documents: {e}")
        return None, None, []
    finally:
        conn.close()


def get_document_list(pg_url: str):
    conn = get_db_connection(pg_url)
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, filename, uploaded_by, uploaded_at, chunk_count, used_ocr FROM documents ORDER BY uploaded_at DESC")
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
            cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        conn.commit()
        return True
    except DatabaseError as e:
        st.error(f"❌ Delete failed: {e}")
        return False
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CHAT HISTORY
# ─────────────────────────────────────────────
def save_chat_message(pg_url: str, username: str, role: str,
                      content: str, sources: Optional[str] = None,
                      confidence: Optional[float] = None):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_history (username, role, content, sources, confidence)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, role, content, sources, confidence))
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
                SELECT role, content, sources, confidence, created_at
                FROM chat_history WHERE username = %s
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
            cur.execute("DELETE FROM chat_history WHERE username = %s", (username,))
        conn.commit()
    except DatabaseError:
        pass
    finally:
        conn.close()


# ─────────────────────────────────────────────
# QUERY LOG & STATS
# ─────────────────────────────────────────────
def log_query(pg_url: str, username: str, query: str,
              response_time_ms: int, confidence: float, success: bool):
    conn = get_db_connection(pg_url)
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO query_log (username, query, response_time_ms, confidence, success)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, query, response_time_ms, confidence, success))
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
            cur.execute("SELECT COUNT(*) FROM documents");       docs    = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM query_log");       queries = cur.fetchone()[0]
            cur.execute("SELECT SUM(chunk_count) FROM documents"); chunks  = cur.fetchone()[0] or 0
            cur.execute("SELECT AVG(confidence) FROM query_log WHERE confidence IS NOT NULL"); avg_conf = cur.fetchone()[0] or 0
        return {"docs": docs, "queries": queries, "chunks": chunks, "avg_conf": round(float(avg_conf) * 100, 1)}
    except DatabaseError:
        return {}
    finally:
        conn.close()
