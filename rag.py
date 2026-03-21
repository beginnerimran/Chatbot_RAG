"""
rag.py — RAG pipeline: PDF extraction, semantic search, confidence, LLM via Groq.
Supports conversation memory and multi-language answers.
"""

import io
import time
from typing import List, Tuple

import numpy as np
import requests
import streamlit as st

try:
    from sentence_transformers import SentenceTransformer
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False

try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False


@st.cache_resource(show_spinner=False)
def load_semantic_model():
    if not SEMANTIC_AVAILABLE:
        return None
    try:
        return SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        st.warning(f"Semantic model failed: {e}. Falling back to keyword search.")
        return None


def extract_text_from_pdf(pdf_bytes: bytes, filename: str) -> Tuple[List[str], bool]:
    chunk_size, overlap = 100, 20
    if PYPDF2_AVAILABLE:
        try:
            reader   = PdfReader(io.BytesIO(pdf_bytes))
            raw_text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    raw_text += t + " "
            words = raw_text.split()
            if len(words) > 50:
                chunks = []
                for i in range(0, len(words), chunk_size - overlap):
                    chunk = ' '.join(words[i:i + chunk_size])
                    if len(chunk.strip()) > 30:
                        chunks.append(chunk)
                return chunks, False
        except Exception:
            pass

    if OCR_AVAILABLE:
        try:
            st.info(f"'{filename}' is scanned — running OCR (~30s per page)...")
            images   = convert_from_bytes(pdf_bytes, dpi=200)
            raw_text = ""
            for img in images:
                raw_text += pytesseract.image_to_string(img, lang='eng') + " "
            words = raw_text.split()
            if len(words) > 20:
                chunks = []
                for i in range(0, len(words), chunk_size - overlap):
                    chunk = ' '.join(words[i:i + chunk_size])
                    if len(chunk.strip()) > 30:
                        chunks.append(chunk)
                return chunks, True
        except Exception as e:
            st.warning(f"OCR failed for '{filename}': {e}")
    else:
        st.warning(f"'{filename}' appears scanned. Install pytesseract + pdf2image for OCR support.")

    return [], False


def semantic_search(query: str, model, all_embeddings: np.ndarray,
                    chunks: List[str], n_results: int = 5) -> Tuple[List[str], List[float]]:
    query_embedding = model.encode([query], normalize_embeddings=True)
    scores          = (query_embedding @ all_embeddings.T).flatten()
    top_indices     = np.argsort(scores)[-n_results:][::-1]
    results, result_scores = [], []
    for idx in top_indices:
        if scores[idx] > 0.15:
            results.append(chunks[idx])
            result_scores.append(float(scores[idx]))
    return results, result_scores


def compute_confidence(scores: List[float]) -> float:
    if not scores:
        return 0.0
    top      = scores[0]
    avg_top3 = np.mean(scores[:3]) if len(scores) >= 3 else np.mean(scores)
    return round(min(float(0.6 * top + 0.4 * avg_top3), 1.0), 3)


def confidence_html(confidence: float) -> str:
    pct = int(confidence * 100)
    if pct >= 65:
        bar_class, label, color = "conf-high",   "High confidence",                          "#00c9a7"
    elif pct >= 35:
        bar_class, label, color = "conf-medium", "Medium confidence",                        "#f0a500"
    else:
        bar_class, label, color = "conf-low",    "Low confidence — answer may be incomplete", "#f05252"
    return f"""
    <div class="conf-wrap">
        <div class="conf-label">Answer Confidence</div>
        <div class="conf-bg"><div class="conf-fill {bar_class}" style="width:{pct}%"></div></div>
        <div class="conf-pct" style="color:{color}">{pct}% — {label}</div>
    </div>"""


def generate_answer(query: str, context: List[str], api_key: str,
                    memory_context: str = "", lang_instruction: str = "") -> Tuple[str, bool]:
    context_text = "\n\n---\n\n".join(context)
    prompt = f"""You are a formal, accurate College AI Assistant for SRM Institute of Science and Technology's Department of Computer Science.

STRICT RULES:
1. Answer ONLY using information explicitly stated in the DOCUMENT CONTEXT below.
2. If the answer is not clearly present, respond ONLY with: "This information is not available in the current documents. Please contact the department office directly."
3. Do NOT guess, infer, or recommend external websites.
4. Be concise and factual.
5. Use bullet points only when listing multiple items.
{lang_instruction}

{memory_context}

DOCUMENT CONTEXT:
{context_text}

STUDENT QUESTION: {query}

ANSWER:"""

    for attempt in range(3):
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile",
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.3, "max_tokens": 600},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('choices') and data['choices'][0].get('message'):
                    return data['choices'][0]['message']['content'], True
                return "Empty response from AI model. Please try again.", False
            elif response.status_code == 401:
                return "Invalid Groq API key.", False
            elif response.status_code == 429:
                if attempt < 2:
                    time.sleep(2 ** attempt); continue
                return "Rate limit reached. Please wait a moment.", False
            elif response.status_code >= 500:
                if attempt < 2:
                    time.sleep(1); continue
                return f"Groq server error ({response.status_code}).", False
            else:
                return f"API error: HTTP {response.status_code}", False
        except requests.exceptions.Timeout:
            if attempt < 2:
                time.sleep(1); continue
            return "Request timed out.", False
        except requests.exceptions.ConnectionError:
            return "Cannot reach Groq API. Check your internet connection.", False
        except Exception as e:
            return f"Unexpected error: {e}", False
    return "All retry attempts failed. Please try again later.", False