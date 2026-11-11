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

> TODO: choose after the user journey.

## 5. Final reflection

> TODO: draft at the end. Notes from the build so far (real problems, in order):

- **Two revisions of the same SOP.** Rev 03 and Rev 04 of QC-SOP-014 give different rules. Fix: read `Document No.` and `Revision` from each PDF header; only the highest revision is searchable; the old one is listed as superseded in the UI.
- **PDF tables.** Plain text extraction put each table cell on its own line. Layout mode kept rows, but cells that wrap ("Maintenance" / "technician") were split across lines, so the model said "a technician". Fix: merge a wrapped line back into its column, using the character position of each column.
- **Embeddings miss codes.** "Alarm AL-104" retrieved the lockout procedure, not the alarm table. Fix: hybrid search, which boosts chunks that contain the exact code from the question.
- **Small model citations are wrong.** qwen2.5:3b often cited the wrong excerpt number (for example, it cited "Purpose" for an alarm answer). Fix: the app picks the source itself, as the excerpts that contain the answer's own words.
- **Forcing JSON made a 3B model worse.** I tried structured output (evidence quotes + answer). The model invented quotes and even changed "monthly" to "quarterly". I went back to plain text. Lesson: test changes with an eval, not by feel. I added `eval.py` (10 questions with expected facts) for this.
- **The model was the limit, not the prompt.** On qwen2.5:3b (8/10), the two failures needed one step of reasoning ("No MTC — can QC start?" means HOLD) or an exception from a second section (lock removal when the owner is absent). Prompt changes moved the score up and down and broke other answers. Switching to qwen3:4b-instruct-2507 (still fits the 4 GB GPU) gave 10/10, but each answer takes ~11 s instead of ~4 s. I chose correctness, because a wrong safety answer costs more than 7 seconds.
- **The "thinking" trap.** The plain `qwen3:4b` tag in Ollama is the thinking-only model: it ignored `think: false` and wrote its reasoning into the answer. The `-instruct-2507` tag is the non-thinking one.
