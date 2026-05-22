# Enterprise PPTX Brand Auditor

A deployed, password-protected PowerPoint review app for Enterprise-style executive compensation presentations.

The app lets a user upload a PPTX, runs deterministic brand and style checks, shows flagged issues in a clean per-slide review panel, supports an optional Gemini AI-assisted judge, and lets the reviewer accept/reject flags before exporting a final audit report.

## Why this design

The case study asks for a solution that combines deterministic code with intelligent AI orchestration, while also minimizing noise, false positives, and incorrect findings.

For this type of brand-compliance workflow, many checks are measurable and should not rely only on an LLM. Layout positions, title rules, terminology, table labels, confidentiality statements, colors, and footnote patterns are better handled with deterministic code because the output is explainable, repeatable, and easier to audit.

The AI layer is intentionally used as a second-pass judge, not as the source of truth. It reviews the visible deterministic findings, helps prioritize the most important issues, identifies potentially noisy rule types, and can suggest a small number of semantic review items. The human reviewer still accepts or rejects every flag.

This design keeps the app practical for production: deterministic code handles rules, AI assists with judgment-heavy review, and the reviewer remains in control.

## Features

- Password-protected Streamlit app
- PPTX upload and per-slide issue review panel
- Deterministic checks based on Enterprise-style brand guidelines
- Optional Gemini AI-assisted judge for second-pass review and prioritization
- Review sensitivity modes to control noise:
  - Conservative - high only
  - Balanced - medium and high
  - Detailed - all findings
- Issue severity, confidence, evidence, and recommendation
- Accept/reject workflow for each flag
- CSV and JSON export
- Annotated-deck support: extracts notes from annotated PPTX files for evaluation/debugging
- Built to scale to future Enterprise decks, not tuned only to the provided samples

## Deterministic + AI-assisted review design

The app uses a deterministic-first workflow for measurable brand rules and an optional AI-assisted judge for second-pass review.

Deterministic checks remain the source of truth because the case study prioritizes correctness, low noise, and explainable findings. The optional LLM judge can be turned on in the sidebar to review visible flags, prioritize the most actionable issues, identify potentially noisy rules, and add up to three advisory semantic findings for human confirmation.

This is intentionally not an auto-fix or auto-accept system. AI output is advisory only, and the reviewer still accepts or rejects every flag.

## Optional AI-assisted judge

For this submission, the deployed AI-assisted judge uses **Gemini 2.5 Flash** through `GEMINI_API_KEY`.

The code also includes provider hooks for OpenAI and Groq so the LLM layer can be swapped without changing the deterministic audit pipeline:

- **Gemini** using `GEMINI_API_KEY` and `gemini-2.5-flash`
- **OpenAI** using `OPENAI_API_KEY` and `gpt-4o-mini`
- **Groq** using `GROQ_API_KEY` and `llama-3.1-8b-instant`

The AI judge does not replace deterministic checks and does not automatically accept or reject findings. It reviews the visible deterministic findings, summarizes what should be prioritized, identifies potentially noisy rule types, and can add a small number of advisory semantic findings for human confirmation.

For Streamlit deployment, add secrets like this:

```toml
APP_PASSWORD = "your-password"

GEMINI_API_KEY = "your-gemini-key"
OPENAI_API_KEY = ""
GROQ_API_KEY = ""

LLM_PROVIDER = "gemini"
LLM_MODEL = "gemini-2.5-flash"
```

## Rule coverage

Implemented checks include:

- Missing confidentiality statement on each slide
- Draft label on title slide
- Slide title ending punctuation
- Long title / headline warning
- Title font size and boldness where detectable
- Content too close to slide edges
- Content extending beyond title bounds
- Bullet punctuation
- `TGT` abbreviation instead of `Target`
- `Percentile` terminology instead of `%ile`
- Possible missing scale labels such as `$MM` or `$000s`
- Table/client/statistics row shading heuristics
- Colors outside the Enterprise palette
- Footnote/source marker mismatch heuristics
- Notes extraction from annotated decks for evaluation and debugging

## Architecture

```text
app.py
  Streamlit UX, authentication, upload, review state, exports, AI judge toggle

src/auditor.py
  Orchestrates PPTX analysis and produces normalized issue objects

src/rules.py
  Brand guideline rules, color palette, severity definitions

src/pptx_utils.py
  Low-level PowerPoint parsing helpers

src/models.py
  Typed data models for slides, issues, reports

src/auth.py
  Password protection

src/slide_preview.py
  Optional local slide preview helper using LibreOffice when available

src/llm_judge.py
  Optional second-pass LLM judge for prioritization, noise review, and semantic findings
```

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Default local password if no environment variable is set:

```text
enterprise-demo-2026
```

For deployment, set `APP_PASSWORD` in Streamlit secrets or platform environment variables.

## How to use

1. Open the app.
2. Enter the password.
3. Upload a PPTX deck.
4. Select review sensitivity.
5. Optional: turn on the AI-assisted judge.
6. Review issues by slide.
7. Accept or reject flags.
8. Export CSV or JSON.

## Framework decisions

- **Streamlit**: fastest way to ship a clean upload/review UX for a case study while keeping the app easy to inspect.
- **python-pptx**: deterministic parsing of slides, shapes, text, tables, notes, fonts, fills, and positions.
- **Deterministic checks first**: keeps measurable brand-compliance checks repeatable, auditable, and low-noise.
- **Gemini AI judge**: uses Gemini 2.5 Flash as an optional second-pass reviewer for prioritization, noise review, and semantic findings.
- **Human-in-the-loop review**: every issue still requires reviewer accept/reject, which prevents the system from blindly trusting model output.

## Suggested production extensions

* Add true slide image overlays with bounding boxes for each issue.
* Add a human feedback loop to learn accepted/rejected flags over time.
* Store audit history by client/deck/version.
* Add formal LLM-as-judge evaluation after deterministic checks pass.
* Add golden-deck regression tests using annotated notes.
* Add role-based authentication and SSO.
* Add client-specific rule profiles for different brand guidelines.
* Add audit trails showing who reviewed each issue and when.