# First prompt to send Claude Code

Copy-paste this verbatim into Claude Code after you've placed `CLAUDE.md`, `docs/PROJECT_SPEC.json`, `docs/PROGRESS.md`, and `docs/RUNBOOK.md` in the project root.

---

Hi Claude. This is the NutriPlan backend project.

Before doing anything, please:

1. Read `CLAUDE.md` end to end — it is your operating manual. Pay particular attention to:
   - Section 2 (workflow protocol)
   - Section 4 (prerequisite gates — run the M0 one)
   - Section 7 (Django architecture & coding standards)
   - Section 8 (hard rules)
   - Section 12 (mandatory context update at the end of every module)
2. Read `docs/PROJECT_SPEC.json` end to end — the single source of truth for *what* to build.
3. Read `docs/PROGRESS.md` to see what's done (empty on first run).
4. Skim `docs/RUNBOOK.md` so you know what to update there as we go.

Then, **do not write any code yet.** Instead, give me four things:

**A. Spec & manual comprehension check** — In your own words (10–14 bullets), summarize:
- What we're building
- The build sequence (M0 → M8) and what each module is responsible for
- The hard rules from `CLAUDE.md` §8
- The workflow loop from `CLAUDE.md` §2
- The mandatory context-update steps from `CLAUDE.md` §12

This is so I can confirm you actually read both documents.

**B. M0 prerequisite gate** — Run `CLAUDE.md` §4 for M0. For each checkbox:
- If you can verify it (e.g., run `python3 --version`), do so and report the result.
- If you can't verify it without my help (e.g., "Postgres user exists"), tell me the exact command for me to run and what to expect.
- If anything fails, STOP and tell me how to fix it using §5 / §6 as the script.

**C. M0 plan** — Per the workflow protocol §2, propose the M0 (`M0_bootstrap`) plan as 5–10 bullets:
- Files to create / modify
- Key functions, classes, or configurations
- Tests to write (even if 0 — explain why)
- Any open questions or ambiguities you want me to clarify before you start

**D. Decisions you need from me before M0 begins**
- Python version: 3.11 or 3.12?
- Package manager: `uv` (recommended), `pip + venv`, or `poetry`?
- Django version pin (latest 5.x stable — propose the exact version).
- Anything else the spec leaves open.

Wait for my confirmation on all four before writing any code.

---

**After M0 finishes**, when you tell me it's done, I expect:
- All §4 / §12 / §8 obligations met.
- §12.1–12.5 of `CLAUDE.md` updated in the same commit as the code.
- A status report per workflow §6.

If any of those are missing when you say "M0 complete," that's a protocol violation — self-correct before asking me to review.
