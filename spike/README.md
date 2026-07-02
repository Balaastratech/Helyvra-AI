# Day-1 Spike — does temporal Cognee work locally?

Prove the riskiest assumption before building anything.

## Run

```bash
cd D:/Balaastra/ideas/total-recall/spike
python -m venv .venv
.venv\Scripts\activate          # PowerShell:  .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then edit .env: set ONE LLM provider + key
python spike_temporal.py
```

First run downloads the local embedding model (fastembed) — that's normal.

## What "success" looks like

- `"before February"` → patient **was** allergic to penicillin
- `"after March"` → patient is **NOT** allergic (allergy cleared 2026-03-02)
- current-truth check → **NOT** allergic

If temporal search distinguishes before/after the supersession date, the whole
project is viable — proceed to Day 2 (self-healing engine).

## If it fails / disappoints

Note exactly how (e.g. temporal ignores dates, or returns both facts equally).
That's a Day-1 win — we adapt the design (e.g. enforce validity windows ourselves
via the `valid_to` field + `ClinicalFact` DataPoint) instead of discovering it on Day 6.

## Notes

- Synthetic data only. Not real PHI. Not medical advice.
- Embeddings run locally (free). Only the cognify/extraction LLM costs money — keep it on a cheap model.
