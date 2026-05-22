# Case Study Requirements Map

| Requirement from Client | Where addressed |
|---|---|
| Deployed app | `app.py`, deployment docs, Dockerfile |
| Password protected | `src/auth.py`, Streamlit secrets/env password |
| Upload PPTX | `app.py` uploader |
| View slides with issues in a clean per-slide panel | `app.py` slide selector and issue cards |
| Quickly accept/reject flags | `app.py` review-state controls |
| Use deterministic code + intelligent orchestration | deterministic `python-pptx` rule engine plus optional `src/llm_judge.py` AI judge toggle |
| Minimize noise / false positives | conservative default sensitivity, severity, confidence, deterministic rules, accept/reject workflow, AI judge is advisory only |
| Correct flagging | notes extraction, deterministic checks, evidence in every issue |
| Not tuned only to samples | generalized rule engine based on brand guidelines |

