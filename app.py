"""SOP Copilot: ask questions about plant SOP PDFs, answered by a local LLM (Ollama) with sources."""
import functools
import json
import math
import os
import re
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
OLLAMA = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM = os.getenv("LLM_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
EMBED = os.getenv("EMBED_MODEL", "nomic-embed-text")
TOP_K = 4

HEADING = re.compile(r"^ (\d{1,2})\. +(\S.*)$")  # section headings have 1 leading space, steps have 2+
NOT_FOUND_MSG = ("I could not find this in the loaded plant documents. "
                 "Please check the QMS or ask the document owner.")

SYSTEM = """You help shop-floor supervisors at a manufacturing plant.
Answer ONLY from the numbered document excerpts. Never use outside knowledge or guess.
- Be short: 1-4 sentences, or a short numbered list for steps.
- Include any exception or special case the excerpts give for the situation.
- Copy numbers, limits, units, codes and job titles exactly as written.
- After each fact, cite the excerpt number like [1].
- If the excerpts do not answer the question, reply with exactly: NOT_FOUND"""


# ---------- loading and chunking ----------

def tidy(lines: list[str]) -> list[str]:
    """Turn layout lines into text. Table rows become 'a | b | c', and a cell that wrapped onto the next
    line is merged back into its column (e.g. 'Maintenance' + 'technician' -> 'Maintenance technician')."""
    out, cols, row = [], None, []
    for line in lines:
        parts = [(m.start(), m.group()) for m in re.finditer(r"\S+(?: {1,2}\S+)*", line)]  # split on 3+ spaces
        if not parts:
            continue
        if cols and parts[0][0] > cols[0] + 2:  # nothing in the first column: continuation of the row above
            for start, text in parts:
                i = min(range(len(cols)), key=lambda c: abs(cols[c] - start))
                row[i] += " " + text
            out[-1] = " | ".join(row)
            continue
        row = [text for _, text in parts]
        cols = [start for start, _ in parts] if len(parts) > 1 else None
        out.append(" | ".join(row))
    return out


def load_pdf(path: Path) -> tuple[dict, list[dict]]:
    """Return (doc metadata, section chunks) for one SOP PDF."""
    pages = [p.extract_text(extraction_mode="layout") for p in PdfReader(path).pages]
    lines = [l for p in pages for l in p.splitlines() if "Uncontrolled copy" not in l]  # drop page footers
    text = "\n".join(lines)
    m = re.search(r"Document No\.\s+(\S+)\s+Revision\s+(\d+)", text)
    doc = {
        "doc_no": m.group(1),
        "rev": int(m.group(2)),
        "title": next(l.strip() for l in lines[1:] if l.strip()),
        "effective": re.search(r"Effective Date\s+(\S+)", text).group(1),
        "file": path.name,
    }
    chunks, section, body = [], "Document details", []
    for line in lines + [" 99. END"]:
        h = HEADING.match(line)
        if h:
            if text := "\n".join(tidy(body)):
                chunks.append({**doc, "section": section, "text": text})
            section, body = f"{h.group(1)}. {h.group(2).strip()}", []
        else:
            body.append(line)
    return doc, chunks


def load_corpus() -> tuple[list[dict], list[dict]]:
    """Load all PDFs. Only the latest revision of each document is searchable; older ones are marked superseded."""
    loaded = [load_pdf(p) for p in sorted(DOCS.glob("*.pdf"))]
    latest = {}
    for doc, _ in loaded:
        latest[doc["doc_no"]] = max(latest.get(doc["doc_no"], 0), doc["rev"])
    docs, chunks = [], []
    for doc, doc_chunks in loaded:
        newest = latest[doc["doc_no"]]
        doc["status"] = "active" if doc["rev"] == newest else f"superseded by Rev {newest:02d}"
        docs.append(doc)
        if doc["rev"] != newest:
            continue
        older = [d["rev"] for d, _ in loaded if d["doc_no"] == doc["doc_no"] and d["rev"] < newest]
        if older:  # improvement: tell the supervisor this SOP changed, so they do not follow the old rule
            history = next((c["text"] for c in doc_chunks if "Revision History" in c["section"]), "")
            row = re.search(rf"^0?{newest} \| [^|]+ \| (.+)$", history, re.M)
            doc["changed"] = {"replaces": f"Rev {max(older):02d}", "date": doc["effective"],
                              "summary": row.group(1) if row else "See the revision history in the PDF."}
            for c in doc_chunks:
                c["changed"] = doc["changed"]
        chunks += doc_chunks
    return docs, chunks


# ---------- Ollama ----------

def ollama(endpoint: str, payload: dict) -> dict:
    req = urllib.request.Request(f"{OLLAMA}/api/{endpoint}", json.dumps(payload).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def embed(texts: list[str]) -> list[list[float]]:
    return ollama("embed", {"model": EMBED, "input": texts})["embeddings"]


def label(c: dict) -> str:
    return f"{c['doc_no']} Rev {c['rev']:02d} - {c['title']} - {c['section']}"


@functools.cache
def index() -> tuple[list[dict], list[dict], list[list[float]]]:
    docs, chunks = load_corpus()
    # nomic-embed-text expects these task prefixes
    vectors = embed([f"search_document: {label(c)}\n{c['text']}" for c in chunks])
    return docs, chunks, vectors


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) / (math.hypot(*a) * math.hypot(*b))


CODE = re.compile(r"\b[A-Z]{2,}(?:-[A-Z]+)*-\d+[A-Z]?\b")  # AL-104, BH-220, QF-07A, SAF-SOP-003


def retrieve(question: str, k: int = TOP_K) -> list[dict]:
    """Hybrid search: embedding similarity, plus a boost for chunks containing exact codes from the question.
    Embeddings alone miss codes like 'AL-104' (they matched lockout text instead of the alarm table)."""
    _, chunks, vectors = index()
    q = embed([f"search_query: {question}"])[0]
    codes = set(CODE.findall(question.upper()))

    def score(cv):
        c, v = cv
        hay = f"{label(c)}\n{c['text']}".upper()
        return cosine(q, v) + (0.3 * sum(code in hay for code in codes) / len(codes) if codes else 0)

    return [c for c, _ in sorted(zip(chunks, vectors), key=score, reverse=True)[:k]]


STOP = set("a an the and or of to in on for is are be it its this that with by as at from if then must should "
           "can may only not no do does what who how when where which there their they".split())


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+(?:[.\-/][a-z0-9]+)*%?", text.lower())) - STOP


def parse_answer(raw: str, hits: list[dict], question: str = "") -> dict:
    """Turn the model's reply into {found, answer, sources}.
    A small model's [n] citations are often wrong, so sources are picked here instead: the excerpts that contain
    the answer's own words (words not already in the question). Kept: the best one, and any at least half as good."""
    raw = raw.strip()
    if not raw or "NOT_FOUND" in raw:
        return {"found": False, "answer": NOT_FOUND_MSG, "sources": []}
    text = re.sub(r"\s*\[\d+\]", "", raw)
    own = words(text) - words(question)
    support = [len(own & words(h["text"])) for h in hits]
    best = max(support)
    keep = sorted((n for n, s in enumerate(support, 1) if s and s >= best / 2), key=lambda n: -support[n - 1])
    return {"found": True, "answer": text, "sources": [{"n": n, **hits[n - 1]} for n in keep or [1]]}


def answer(question: str) -> dict:
    hits = retrieve(question)
    context = "\n\n".join(f"[{i}] {label(c)}\n{c['text']}" for i, c in enumerate(hits, 1))
    reply = ollama("chat", {
        "model": LLM,
        "stream": False,
        "think": False,  # hybrid models like qwen3 would otherwise "think" first and be slow
        "options": {"temperature": 0, "num_ctx": 4096},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Excerpts:\n\n{context}\n\nQuestion: {question}"},
        ],
    })["message"]["content"]
    return parse_answer(reply, hits, question)


# ---------- API ----------

@asynccontextmanager
async def lifespan(_app):
    index()  # load PDFs and embed them once at startup
    yield


app = FastAPI(title="SOP Copilot", lifespan=lifespan)
app.mount("/pdf", StaticFiles(directory=DOCS), name="pdf")


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/documents")
def documents():
    return index()[0]


@app.post("/api/ask")
def ask(body: Ask):
    return answer(body.question.strip())
