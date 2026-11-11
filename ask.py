"""Ask questions from the command line and print Markdown (used for the README answers).
Usage: python ask.py "question 1" "question 2" ..."""
import sys
import time

from app import answer

for q in sys.argv[1:]:
    t = time.time()
    r = answer(q)
    print(f"**Q: {q}**\n\n{r['answer']}\n")
    for s in r["sources"]:
        print(f"- Source: {s['doc_no']} Rev {s['rev']:02d}, {s['section']}")
    print(f"\n_{time.time() - t:.1f} s_\n")
