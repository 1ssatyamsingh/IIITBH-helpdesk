# CS474 Major Project Report (P9 — Campus Helpdesk Chatbot with RAG)

LaTeX source for the team report. Single file: `main.tex`.

## Compile on Overleaf (recommended)

1. Create a new Overleaf project → **New Project → Upload Project**.
2. Zip this `report/` folder and upload it (or drag `main.tex` into a blank project).
3. Set the compiler to **pdfLaTeX** (Menu → Compiler) and TeX Live version to the latest available.
4. Compile. The output is a ~20-page PDF with title page, TOC, 4 diagrams, tables, references and appendices.

No images are needed — all figures are TikZ, so the single `.tex` file is self-contained.

## Compile locally (optional)

```powershell
pdflatex main.tex
pdflatex main.tex   # second run resolves the table of contents and references
```

## Before submitting — fill in the red placeholders

Every red `[TODO: ...]` in the PDF must be resolved. The complete list is in
**Appendix D — Fill-in Checklist** at the end of the report (delete that
appendix before the final submission). Summary:

| Where | What to fill |
|---|---|
| Title page | 10th team member's name |
| Table 1 (P9 mapping) | fine-tuning status, deployment URL, dataset path, eval/Langfuse status |
| Table 3 (corpus) | category percentage breakdown of the 96 files |
| Sec. 3.4 | final answerable/unanswerable split + dataset file location in the repo |
| Sec. 7 | measured TTFT / end-to-end latency |
| Sec. 8 | judge model name, judge–human agreement, **results tables (run the 200-pair evaluation)**, discussion paragraphs |
| Sec. 9 | Langfuse integration status + 1–2 trace screenshots |
| Sec. 10 | end-to-end manual test date/result |
| Sec. 11 | role assignments per member, repo URL, per-member weekly commit table |
| Sec. 12 | deployment URL (or note that the demo runs locally) |

## Notes

- Do **not** commit generated PDFs or aux files if you prefer a clean repo
  (the root `.gitignore` should list `report/*.aux`, `*.log`, `*.out`, `*.toc`).
- The report content is written from the actual repository state
  (FastAPI + React + Qdrant RAG, 96-file / 1,582-chunk corpus, SSE streaming,
  backend-validated citations, guardrails, live search, 59 pytest tests).
  Re-check any numbers if the corpus or test count changes.
