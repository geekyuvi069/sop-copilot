"""Self-check for the parts that do not need Ollama. Run: python test_app.py"""
from app import load_corpus, parse_answer

docs, chunks = load_corpus()
status = {(d["doc_no"], d["rev"]): d["status"] for d in docs}
assert status[("QC-SOP-014", 4)] == "active"
assert status[("QC-SOP-014", 3)] == "superseded by Rev 04"
assert not any(c["doc_no"] == "QC-SOP-014" and c["rev"] == 3 for c in chunks), "old revision must not be searchable"
# improvement: chunks of a document that replaced an older revision carry a "what changed" note
qc = next(c for c in chunks if c["doc_no"] == "QC-SOP-014")
assert qc["changed"]["replaces"] == "Rev 03" and "MTC made mandatory" in qc["changed"]["summary"], qc["changed"]
assert not any("changed" in c for c in chunks if c["doc_no"] != "QC-SOP-014")

sections = {(c["doc_no"], c["section"]): c["text"] for c in chunks}
assert "AL-104" in sections[("MNT-MAN-CNC-02", "6. Common Alarms")]  # table split across a page break stays together
assert "Production Manager" in sections[("SAF-SOP-003", "6. Removal of a Lock When the Owner Is Absent")]
# wrapped table cells are merged back into their column
assert "fan filter | Maintenance technician" in sections[("MNT-MAN-CNC-02", "4. Preventive Maintenance Schedule")]
assert "Call maintenance if pressure stays below 3.5 MPa." in sections[("MNT-MAN-CNC-02", "6. Common Alarms")]
for doc_no in {c["doc_no"] for c in chunks}:  # numbered steps restart at 1, so a step taken as a heading breaks this
    nums = [int(c["section"].split(".")[0]) for c in chunks if c["doc_no"] == doc_no and c["section"][0].isdigit()]
    assert nums == sorted(set(nums)), (doc_no, nums)

hits = [{"text": "This manual covers TX-200 turning centres."},
        {"text": "AL-412 | Coolant level low | Top up coolant mixed to 6 - 8 % concentration."},
        {"text": "Way lube oil | ISO VG 68 | Visual, top-up as needed"}]
assert parse_answer("NOT_FOUND", hits)["found"] is False
assert parse_answer("  ", hits)["found"] is False
r = parse_answer("It means coolant level low. Top up coolant mixed to 6 - 8 % [1].", hits, "What does AL-412 mean?")
assert r["answer"] == "It means coolant level low. Top up coolant mixed to 6 - 8 %.", r["answer"]  # [n] removed
assert [s["n"] for s in r["sources"]] == [2]  # the model cited [1], but the words come from excerpt 2
r = parse_answer("Top up coolant mixed to 6 - 8 %. Way lube is ISO VG 68.", hits, "coolant and lube?")
assert sorted(s["n"] for s in r["sources"]) == [2, 3]
print("ok")
