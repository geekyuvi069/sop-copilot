# SOP Copilot

A small copilot for shop-floor supervisors. Ask a question in plain words, get a short answer taken **only** from the plant's SOP PDFs, with the source document, revision and section shown. If the documents do not cover the question, it says so instead of guessing.

- **Backend:** FastAPI (`app.py`, ~150 lines)
- **UI:** one HTML page, no build step, works on a phone (`static/index.html`)
- **LLM:** `qwen2.5:3b`, local, through [Ollama](https://ollama.com) (runs on a 4 GB GTX 1650)
- **Embeddings:** `nomic-embed-text`, local, through Ollama
- **No vector database:** 4 PDFs give 25 chunks, so they are embedded at startup and searched in memory.

See [THINKING.md](THINKING.md) for the user research, user journey, AI critique and reflection.

## How it works

1. **Load:** `pypdf` (layout mode) reads each PDF in `docs/`. Page footers are removed and wide table gaps become ` | `, so table rows stay on one line.
2. **Chunk by section:** the SOPs use numbered headings (`4. Lockout Procedure`). One section = one chunk, so a procedure or a table is never cut in half (the alarm table runs across a page break and still stays in one chunk).
3. **Revision control:** the header of each PDF gives `Document No.` and `Revision`. If two files have the same document number (here `QC-SOP-014` Rev 03 and Rev 04), only the highest revision is searchable. The older one is shown in the UI as superseded.
4. **Retrieve:** cosine similarity on embeddings, **plus a boost for exact codes** in the question (`AL-104`, `BH-220`, `QF-07A`). Embeddings alone sent "alarm AL-104" to the lockout procedure, so the boost is needed.
5. **Answer:** the top 4 sections go to the LLM with numbered labels. The model must answer only from them, copy numbers exactly, cite `[n]`, or reply `NOT_FOUND`. Temperature is 0.
6. **Show sources:** the UI shows only the sections the model cited, with document number, revision, effective date, section, the exact excerpt, and a link to open the PDF.

## Setup

Needs Python 3.10+ and Ollama.

```bash
# 1. Models (about 2.2 GB in total)
ollama pull qwen2.5:3b
ollama pull nomic-embed-text

# 2. Python
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Run (0.0.0.0 makes it reachable from other devices on the Wi-Fi)
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` on the laptop.

### Open it from your phone

1. Connect the phone to the same Wi-Fi as the laptop.
2. Find the laptop's IP: `hostname -I` (Linux) or `ipconfig getifaddr en0` (macOS). Example: `192.168.31.15`.
3. Open `http://192.168.31.15:8000` on the phone.
4. If it does not load, the firewall is blocking the port. On Ubuntu, allow only the local network:
   ```bash
   sudo ufw allow from 192.168.31.0/24 to any port 8000 proto tcp
   ```

### Settings (optional)

| Env var | Default | Use |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `LLM_MODEL` | `qwen2.5:3b` | Any Ollama chat model, e.g. `llama3.2:3b` |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model |

To add documents, put PDFs in `docs/` and restart.

### Check

```bash
.venv/bin/python test_app.py   # chunking, revision handling, answer parsing (no Ollama needed)
.venv/bin/python ask.py "Who is allowed to remove a lockout lock?"   # ask from the terminal
```

## Test results

<!-- ANSWERS -->
