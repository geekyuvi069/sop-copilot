# SOP Copilot

A small copilot for shop-floor supervisors. Ask a question in plain words, get a short answer taken **only** from the plant's SOP PDFs, with the source document, revision and section shown. If the documents do not cover the question, it says so instead of guessing.

- **Backend:** FastAPI (`app.py`, ~200 lines)
- **UI:** one HTML page, no build step, works on a phone (`static/index.html`)
- **LLM:** `qwen3:4b-instruct-2507` (Q4_K_M, 2.5 GB), local, through [Ollama](https://ollama.com). Runs fully on a 4 GB GTX 1650.
- **Embeddings:** `nomic-embed-text`, local, through Ollama
- **No vector database:** 4 PDFs give 25 chunks, so they are embedded at startup and searched in memory.

See [THINKING.md](THINKING.md) for the user research, user journey, AI critique and reflection.

## How it works

1. **Load:** `pypdf` (layout mode) reads each PDF in `docs/`. Page footers are removed and wide table gaps become ` | `, so table rows stay on one line.
2. **Chunk by section:** the SOPs use numbered headings (`4. Lockout Procedure`). One section = one chunk, so a procedure or a table is never cut in half (the alarm table runs across a page break and still stays in one chunk).
3. **Revision control:** the header of each PDF gives `Document No.` and `Revision`. If two files have the same document number (here `QC-SOP-014` Rev 03 and Rev 04), only the highest revision is searchable. The older one is shown in the UI as superseded.
4. **Retrieve:** cosine similarity on embeddings, **plus a boost for exact codes** in the question (`AL-104`, `BH-220`, `QF-07A`). Embeddings alone sent "alarm AL-104" to the lockout procedure, so the boost is needed.
5. **Answer:** the top 4 sections go to the LLM. It must answer only from them, copy numbers exactly, include exceptions, or reply `NOT_FOUND`. Temperature is 0.
6. **Pick sources:** small models often cite the wrong excerpt number, so the app does not trust the model's `[n]`. A source is any excerpt that contains the answer's own words (words not already in the question). The UI shows document number, revision, effective date, section, the exact excerpt, and a link to open the PDF.
7. **Improvement — "this SOP changed" alert:** if the answer comes from a document that replaced an older revision, the card shows a yellow alert with the date and what changed (from the revision history table), and says old printed copies are not valid. Why: see THINKING.md §4.

## Setup

Needs Python 3.10+ and Ollama.

```bash
# 1. Models (about 2.8 GB in total)
ollama pull qwen3:4b-instruct-2507-q4_K_M
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
| `LLM_MODEL` | `qwen3:4b-instruct-2507-q4_K_M` | Any Ollama chat model, e.g. `qwen2.5:3b` (faster, less accurate) |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model |

To add documents, put PDFs in `docs/` and restart.

### Check

```bash
.venv/bin/python test_app.py   # chunking, revision handling, answer parsing (no Ollama needed)
.venv/bin/python eval.py       # 10 questions, checks each answer for the key facts
.venv/bin/python ask.py "Who is allowed to remove a lockout lock?"   # ask from the terminal
```

## Test results

`eval.py` runs 10 questions (the 5 sample questions + my 5) and checks each answer for the key facts. On a laptop with a GTX 1650 (4 GB):

| Model | Passed | Time per answer |
|---|---|---|
| `qwen2.5:3b` | 8 / 10 (missed the absent-owner lock rule and the missing-MTC HOLD) | ~4 s |
| **`qwen3:4b-instruct-2507`** (default) | **10 / 10** | ~11 s |

For safety and quality answers, I chose correct over fast.

### Sample questions

| # | Question | App's answer | Source |
|---|---|---|---|
| 1 | What is the recommended coolant concentration for the TX-200 CNC turning centre? | The recommended coolant concentration for the TX-200 CNC turning centre is 6 - 8 %. | MNT-MAN-CNC-02 Rev 02, §3 Normal Operating Parameters (+ §6 Common Alarms) |
| 2 | The machine is showing alarm AL-104. What does it mean and what should the operator do? | AL-104 means Way lube oil level low. The operator should top up with ISO VG 68 oil to the MAX mark, then press RESET. The machine can continue after reset. | MNT-MAN-CNC-02 Rev 02, §6 Common Alarms |
| 3 | Who is allowed to remove a lockout lock from a machine? | 1. Each authorised person removes only their own lock. Nobody may remove another person's lock. 2. If the lock owner is absent, the lock may be removed only if the Shift Supervisor contacts the owner, and if the owner cannot be reached, both the Production Manager and the Safety Officer must authorise removal. | SAF-SOP-003 Rev 05, §5 Removing Locks + §6 Removal of a Lock When the Owner Is Absent |
| 4 | What is the outer diameter tolerance for the BH-220 bearing housing? | The outer diameter tolerance for the BH-220 bearing housing is +/- 0.050. | QC-SOP-014 **Rev 04**, §6 Inspection Dimensions (only in Rev 04) |
| 5 | How often should spindle runout be checked, and who does it? | Monthly \| Maintenance technician | MNT-MAN-CNC-02 Rev 02, §4 Preventive Maintenance Schedule |

### My own 5 questions

| # | Question | Why I asked it | App's answer | Source |
|---|---|---|---|---|
| 6 | CNC-06 shows alarm AL-101 and the pressure gauge reads 3.2 MPa. What should we do? | Needs two sections: the alarm table and the normal range. | AL-101 means Hydraulic pressure low. The pressure gauge reads 3.2 MPa, which is below the normal range of 3.5 - 4.0 MPa. Stop cycle. Check oil level and pressure gauge. Call maintenance if pressure stays below 3.5 MPa. | MNT-MAN-CNC-02 Rev 02, §6 + §3 |
| 7 | A lot of 400 castings arrived without a material test certificate. Can QC start the inspection? | The question does not use the word "HOLD"; the answer needs one step of reasoning. Rev 03 has no such rule. | No, QC cannot start the inspection because the Material Test Certificate (MTC) is missing and mandatory. The lot must be put on HOLD until the MTC is received. | QC-SOP-014 Rev 04, §5 Procedure |
| 8 | Where do rejected materials go, and who must be informed? | **Revision trap:** Rev 03 says "Red Bin near Gate 2, inform Purchase". Rev 04 says something else. | Rejected materials go to Quarantine Cage Q1, Stores Bay 3. The Shift QC Supervisor must inform the Supplier Quality Engineer (SQE) within 4 hours of rejection. | QC-SOP-014 **Rev 04**, §5 Procedure |
| 9 | Which oil goes in the hydraulic system, and is it the same as the way lube oil? | Two similar oils (ISO VG 46 and VG 68) in one manual; easy to mix up. | The hydraulic system uses hydraulic oil (ISO VG 46). The way lube oil is ISO VG 68. The oils are not the same. | MNT-MAN-CNC-02 Rev 02, §4 + §3 |
| 10 | What is the maximum spindle speed of the TX-200? | **Not in the documents.** The manual is about the TX-200, so a model could easily guess a number. | I could not find this in the loaded plant documents. Please check the QMS or ask the document owner. | none |

Answers are copied from `python ask.py ...` output (same run as the table above). Answer 5 is terse because the model copied the table row; it is correct but not a full sentence.

## AI use

I used Claude Code as a coding assistant while building this. I reviewed every part and can explain all of it. The user journey draft in THINKING.md is my own, written before using AI, as the brief asks.

