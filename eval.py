"""Run the sample questions + our own questions and check each answer for the key facts.
Usage: python eval.py            (LLM_MODEL=qwen3:4b python eval.py to try another model)"""
import re
import time

from app import LLM, answer

# (question, regexes that must all appear in the answer; None = the app must say "not found")
CASES = [
    # sample questions from BiztelAI
    ("What is the recommended coolant concentration for the TX-200 CNC turning centre?", [r"6\s*-\s*8\s*%"]),
    ("The machine is showing alarm AL-104. What does it mean and what should the operator do?",
     [r"way lube", r"VG 68", r"reset"]),
    ("Who is allowed to remove a lockout lock from a machine?", [r"own lock", r"production manager", r"safety officer"]),
    ("What is the outer diameter tolerance for the BH-220 bearing housing?", [r"0\.050?"]),
    ("How often should spindle runout be checked, and who does it?", [r"monthly", r"maintenance technician"]),
    # our own questions
    ("CNC-06 shows alarm AL-101 and the pressure gauge reads 3.2 MPa. What should we do?", [r"stop", r"maintenance"]),
    ("A lot of 400 castings arrived without a material test certificate. Can QC start the inspection?", [r"hold"]),
    ("Where do rejected materials go, and who must be informed?", [r"Q1", r"SQE|Supplier Quality", r"4 hours"]),
    ("Which oil goes in the hydraulic system, and is it the same as the way lube oil?", [r"VG 46", r"VG 68"]),
    ("What is the maximum spindle speed of the TX-200?", None),
]

passed, start = 0, time.time()
for q, must in CASES:
    r = answer(q)
    ok = (not r["found"]) if must is None else r["found"] and all(re.search(m, r["answer"], re.I) for m in must)
    passed += ok
    print(f"{'PASS' if ok else 'FAIL'} | {q}\n       {r['answer'][:300]!r}")
    print("       sources:", "; ".join(f"{s['doc_no']} {s['section']}" for s in r["sources"]) or "-", "\n")
print(f"{LLM}: {passed}/{len(CASES)} passed, {(time.time() - start) / len(CASES):.1f} s per question")
