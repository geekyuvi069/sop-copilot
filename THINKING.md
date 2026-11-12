# THINKING.md

## 1. Understand the user

**Who:** a shift supervisor at Kaveri Precision Components, Hosur, a precision machining plant (CNC turning, incoming inspection of castings, forgings and bought-out parts). Assumptions, since I have no plant access:

- They run one shift (8–12 hours) with about 15–40 operators, several CNC machines and a receiving area.
- They are experienced on the floor (diploma or ITI plus years of shop-floor work), not a document author. They know the machines well, but they do not remember every limit, revision change or rare procedure.
- They carry an Android phone. They often wear gloves, the floor is loud, and Wi-Fi is weak in some bays.
- They speak English for work terms, but often think in Tamil or Hindi. Short, plain answers work best.
- Night shifts have no engineer or QC manager on site, so the supervisor makes the call.

**What they are trying to do during a shift:**

- Keep output on plan: clear machine alarms fast and decide "can we continue or stop?".
- Keep people safe: follow lockout/tagout before maintenance, and handle exceptions (for example, a lock left on by someone who went home).
- Keep bad material out: decide if an incoming lot can be inspected, held or rejected, and who to inform.
- Answer operators' questions ("what concentration?", "what torque?") without walking to the office.

**What frustrates them today:**

- The answer is in a PDF on the QMS, which is a desktop in the office, far from the machine.
- Printed copies get old. The footer says "Uncontrolled copy when printed", and the sample set itself has two revisions of QC-SOP-014 that disagree (5 samples for all lots vs a lot-size table; paper form vs app; Red Bin vs Quarantine Cage Q1).
- Finding one number in a long document takes minutes, and the line waits.
- The person who knows (maintenance engineer, SQE, safety officer) is often not on shift.
- For safety and quality rules, a wrong or old answer is worse than no answer, so they do not trust a tool that guesses.

**What this means for the copilot:**

1. Answers must come only from the documents, and must show the source (document, revision, section) so the supervisor can check them.
2. Only the current revision may be used. An old revision must never answer silently.
3. "Not in the documents" is a valid and important answer.
4. Phone first: big touch targets, short answers, fast.

## 2. User journey

> TODO (Yuvraj): first draft written by me, before using AI.

## 3. AI challenge

> TODO (Yuvraj): key parts of the AI critique of my journey, then what I agreed with, disagreed with, and changed.

## 4. The improvement I added, and why

**What:** a **"this SOP changed" alert**. When an answer comes from a document that replaced an older revision, the answer card shows a yellow box:

> ⚠ QC-SOP-014 changed on 01-Jul-2026. Rev 04 replaces Rev 03. Old printed copies are not valid. What changed: Lot-size based sampling plan; MTC made mandatory; quarantine moved to Cage Q1; digital form QF-07A; 4-hour SQE escalation; BH-220 critical dimensions added.

The text comes from the revision history table of the new revision, not from the AI.

**Why this one:**

- The base app already answers only from Rev 04, so the answer is correct. But a supervisor who learned Rev 03 (5 samples for every lot, Red Bin near Gate 2, inform Purchase) gets an answer that **differs from what they remember**. A correct answer that looks wrong is not trusted: they follow their memory or the old printed copy. The alert explains *why* the answer is different and tells them the old copy is void.
- Rev 04 changed six things the floor does every day. This is the highest-risk moment in the sample documents.
- It has no AI risk: it is plain document text, so it cannot be hallucinated.
- It is small (about 15 lines) and has a test.

**What I did not choose, and why:**

- *Voice input* (gloves, noise): browsers allow the microphone only on HTTPS or localhost, so it would not work on the phone over plain LAN HTTP without setting up certificates.
- *Streaming the answer* (to hide the ~11 s wait): useful, and next on my list, but it does not change what the supervisor does.
- *Tamil/Hindi answers*: a 4B model is not reliable enough in Tamil for safety text.

**Limit:** it works only when the older revision is also loaded and the new one has a revision history table.

## 5. Final reflection

**What I would build next**

1. **Stream the answer** word by word, so text appears after ~2 s instead of a blank wait of ~11 s.
2. **Show the exact SOP sentence** under the answer, checked against the PDF text, so for safety steps the supervisor reads the original wording, not a summary.
3. **"Wrong / not helpful" button** that logs the question and answer for the document owner. Questions the documents cannot answer also show gaps in the SOPs.
4. **Connect to the QMS** so only released revisions are loaded, instead of a folder of PDFs.
5. **Scale to hundreds of SOPs:** a real vector store (for example SQLite with a vector extension), a reranker, and filters by machine or area. In-memory search is fine for 25 chunks, not for thousands.

**What I am unsure about**

- If ~11 s per answer is acceptable on the floor. I would measure it with real supervisors.
- If supervisors will type at all, or if voice is required.
- Chunking depends on the numbered headings of these four PDFs. Scanned PDFs or tables as images would need OCR and a different splitter.
- Picking sources by word overlap works here, but it can choose the wrong section when two sections share many words.
- My eval has only 10 questions that I wrote myself, so 10/10 is a smoke test, not an accuracy number.

**What I would ask the customer**

- How are SOPs released and withdrawn today? Who owns each one, and how often do they change?
- For safety procedures like LOTO, may the copilot summarise, or must it only show the original steps?
- Wi-Fi coverage on the floor, which devices (shared tablets or personal phones), and which languages?
- Who may see which documents (role-based access)?
- When an SOP is unclear today, who does the supervisor call? Should the app hand over to that person?
- Must data stay on site? (This is why I used a local model.)

**Challenges and how I handled them**

The **biggest challenge was making a small local model reliable**. My first model (qwen2.5:3b) answered fast but missed exceptions and simple reasoning, and its citations pointed to the wrong sections. Each prompt change fixed one answer and broke another. What worked: I stopped tuning by feel and wrote `eval.py` (10 questions with the facts each answer must contain), fixed the problems that were really in my data (tables, codes), moved source picking out of the model, and then compared models on the same eval. qwen3:4b-instruct went from 8/10 to 10/10 on the same 4 GB GPU, but it is slower.

Other problems, in the order I met them:

- **Two revisions of the same SOP.** Rev 03 and Rev 04 of QC-SOP-014 give different rules. Fix: read `Document No.` and `Revision` from each PDF header; only the highest revision is searchable; the old one is listed as superseded in the UI.
- **PDF tables.** Plain text extraction put each table cell on its own line. Layout mode kept rows, but cells that wrap ("Maintenance" / "technician") were split across lines, so the model said "a technician". Fix: merge a wrapped line back into its column, using the character position of each column.
- **Embeddings miss codes.** "Alarm AL-104" retrieved the lockout procedure, not the alarm table. Fix: hybrid search, which boosts chunks that contain the exact code from the question.
- **Small model citations are wrong.** qwen2.5:3b often cited the wrong excerpt number (for example, it cited "Purpose" for an alarm answer). Fix: the app picks the source itself, as the excerpts that contain the answer's own words.
- **Forcing JSON made a 3B model worse.** I tried structured output (evidence quotes + answer). The model invented quotes and even changed "monthly" to "quarterly". I went back to plain text. Lesson: test changes with an eval, not by feel. I added `eval.py` (10 questions with expected facts) for this.
- **The model was the limit, not the prompt.** On qwen2.5:3b (8/10), the two failures needed one step of reasoning ("No MTC — can QC start?" means HOLD) or an exception from a second section (lock removal when the owner is absent). Prompt changes moved the score up and down and broke other answers. Switching to qwen3:4b-instruct-2507 (still fits the 4 GB GPU) gave 10/10, but each answer takes ~11 s instead of ~4 s. I chose correctness, because a wrong safety answer costs more than 7 seconds.
- **The "thinking" trap.** The plain `qwen3:4b` tag in Ollama is the thinking-only model: it ignored `think: false` and wrote its reasoning into the answer. The `-instruct-2507` tag is the non-thinking one.
- **Greeting echo (found while testing on the phone).** Typing "hii" made the model echo "hii", and the app showed it as an answer with a random source. Fix: a grounding check — if the answer shares no words with any excerpt, the app shows "not found" — plus a prompt rule for greetings. Eval still 10/10.
- **Deploying on the LAN.** uvicorn must listen on `0.0.0.0`, not `127.0.0.1`, or the phone cannot connect. Ubuntu's firewall (ufw) is on, so I allowed port 8000 only from the local network (`192.168.31.0/24`), not from everywhere.
