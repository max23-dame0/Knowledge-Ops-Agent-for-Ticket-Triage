"""Try to salvage old tobi checkpoints written with random-salted hash()."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from src.evals.ticket_bench.bench_core import load_tobi

CKPT_DIR = Path("data/eval_results/backup_resume_fail")


def stable_sid(idx: int, text: str) -> tuple[int, str]:
    return (idx, hashlib.md5(text[:80].encode("utf-8")).hexdigest())


def main() -> None:
    samples = load_tobi(0)
    by_key = {}
    for idx, s in enumerate(samples):
        by_key.setdefault((idx, s["text"][:80]), s)

    for ckpt in sorted(CKPT_DIR.glob("ticket_full_*_tobi_ckpt.jsonl")):
        rows = [json.loads(l) for l in ckpt.read_text(encoding="utf-8").splitlines() if l.strip()]
        matched = 0
        new_rows = []
        dup = 0
        seen = set()
        for r in rows:
            if not r.get("ok"):
                continue
            idx = r["sample_id"][0]
            text80 = r.get("text", "")[:80]
            key = (idx, text80)
            s = by_key.get(key)
            if s is None:
                continue
            new_sid = stable_sid(idx, s["text"])
            if new_sid in seen:
                dup += 1
                continue
            seen.add(new_sid)
            r["sample_id"] = list(new_sid)
            r.setdefault("content_len", 0)
            new_rows.append(r)
            matched += 1
        ok_total = sum(1 for r in rows if r.get("ok"))
        print(f"{ckpt.name}: rows={len(rows)} ok={ok_total} matched={matched} dups={dup}")
        out = CKPT_DIR / ckpt.name.replace("_ckpt", "_salvaged_ckpt")
        with out.open("w", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  -> salvaged: {out} ({matched} rows)")


if __name__ == "__main__":
    main()
