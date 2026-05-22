from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any

import streamlit as st

from .models import AuditReport, Issue


@dataclass
class LLMJudgeResult:
    enabled: bool
    available: bool
    provider: str
    model: str
    summary: str
    reviewed_issue_count: int
    high_priority_rule_ids: list[str]
    possible_noise_rule_ids: list[str]
    semantic_findings: list[dict[str, Any]]
    raw_response: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _secret_or_env(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name)


def get_llm_config(provider: str, model: str | None = None) -> tuple[bool, str, str, str | None, str]:
    """Return (available, provider, model, api_key, endpoint)."""
    provider = (provider or "OpenAI").strip()
    if provider == "Groq":
        return (
            bool(_secret_or_env("GROQ_API_KEY")),
            "Groq",
            model or _secret_or_env("GROQ_MODEL") or "llama-3.1-8b-instant",
            _secret_or_env("GROQ_API_KEY"),
            "https://api.groq.com/openai/v1/chat/completions",
        )
    if provider == "Gemini":
        gemini_key = _secret_or_env("GEMINI_API_KEY") or _secret_or_env("GOOGLE_API_KEY")
        gemini_model = model or _secret_or_env("GEMINI_MODEL") or "gemini-1.5-flash"
        return (
            bool(gemini_key),
            "Gemini",
            gemini_model,
            gemini_key,
            f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key or ''}",
        )
    return (
        bool(_secret_or_env("OPENAI_API_KEY")),
        "OpenAI",
        model or _secret_or_env("OPENAI_MODEL") or "gpt-4o-mini",
        _secret_or_env("OPENAI_API_KEY"),
        "https://api.openai.com/v1/chat/completions",
    )


def _call_chat_completion(provider: str, model: str, api_key: str, endpoint: str, messages: list[dict[str, str]], timeout: int = 45) -> str:
    if provider == "Gemini":
        # Gemini uses a different API shape from OpenAI-compatible providers.
        # Keep the same system/user messages, but ask for JSON MIME output.
        prompt_text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt_text}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError(f"Gemini returned no candidates: {data}")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise ValueError(f"Gemini returned no text content: {data}")
        return parts[0]["text"]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _safe_json_loads(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return {}


def _compact_issue(issue: Issue) -> dict[str, Any]:
    return {
        "slide": issue.slide_number,
        "rule_id": issue.rule_id,
        "severity": issue.severity,
        "category": issue.category,
        "title": issue.title,
        "evidence": issue.evidence[:260],
        "recommendation": issue.recommendation[:220],
        "confidence": round(issue.confidence, 2),
    }


def build_llm_payload(report: AuditReport, issues: list[Issue], max_issues: int = 25) -> dict[str, Any]:
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    selected = sorted(issues, key=lambda i: (severity_rank[i.severity], -i.confidence, i.slide_number))[:max_issues]
    slide_titles = {s.slide_number: s.title for s in report.slide_summaries[:60]}
    return {
        "file_name": report.file_name,
        "slide_count": report.slide_count,
        "reviewed_issues": [_compact_issue(i) for i in selected],
        "slide_titles": slide_titles,
    }


def run_llm_judge(report: AuditReport, issues: list[Issue], provider: str = "OpenAI", model: str | None = None, max_issues: int = 25) -> LLMJudgeResult:
    available, provider_name, model_name, api_key, endpoint = get_llm_config(provider, model)
    if not available or not api_key:
        return LLMJudgeResult(
            enabled=True,
            available=False,
            provider=provider_name,
            model=model_name,
            summary="AI judge is enabled, but no API key is configured. Add OPENAI_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY in Streamlit secrets to run the optional AI layer.",
            reviewed_issue_count=0,
            high_priority_rule_ids=[],
            possible_noise_rule_ids=[],
            semantic_findings=[],
            error="Missing API key",
        )

    payload = build_llm_payload(report, issues, max_issues=max_issues)
    system = """
You are an AI quality-control reviewer for an executive compensation PPTX brand-audit tool.
Your job is NOT to replace deterministic checks. Your job is to act as a second-pass judge.
Prioritize low noise, correct flagging, and human-review usefulness.
Do not invent brand rules. Use only the issue evidence and slide titles provided.
Return JSON only.
""".strip()
    user = f"""
Review this deterministic PPTX audit output. Return JSON with:
- summary: 2-4 sentences explaining whether the findings look useful/noisy.
- high_priority_rule_ids: rule_ids the reviewer should prioritize first.
- possible_noise_rule_ids: rule_ids that may be noisy or need human confirmation.
- semantic_findings: up to 3 additional judgment-heavy findings, each with slide_number, title, severity, evidence, recommendation. Only include if clearly supported by the provided slide titles/issues.

Audit payload:
{json.dumps(payload, indent=2)}
""".strip()

    try:
        raw = _call_chat_completion(
            provider=provider_name,
            model=model_name,
            api_key=api_key,
            endpoint=endpoint,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        data = _safe_json_loads(raw)
        semantic = data.get("semantic_findings") or []
        if not isinstance(semantic, list):
            semantic = []
        return LLMJudgeResult(
            enabled=True,
            available=True,
            provider=provider_name,
            model=model_name,
            summary=str(data.get("summary") or "AI judge completed."),
            reviewed_issue_count=len(payload["reviewed_issues"]),
            high_priority_rule_ids=[str(x) for x in data.get("high_priority_rule_ids", []) if x],
            possible_noise_rule_ids=[str(x) for x in data.get("possible_noise_rule_ids", []) if x],
            semantic_findings=semantic[:3],
            raw_response=raw,
        )
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")[:600]
        return LLMJudgeResult(True, False, provider_name, model_name, f"AI judge request failed: HTTP {e.code}.", 0, [], [], [], error=detail)
    except Exception as e:
        return LLMJudgeResult(True, False, provider_name, model_name, f"AI judge request failed: {e}", 0, [], [], [], error=str(e))


def semantic_findings_to_issues(findings: list[dict[str, Any]]) -> list[Issue]:
    issues: list[Issue] = []
    for item in findings[:3]:
        try:
            slide_number = int(item.get("slide_number") or item.get("slide") or 1)
        except Exception:
            slide_number = 1
        severity = str(item.get("severity") or "low").lower()
        if severity not in {"high", "medium", "low"}:
            severity = "low"
        issues.append(Issue(
            slide_number=slide_number,
            rule_id="AI_SEMANTIC_REVIEW",
            category="AI-assisted review",
            severity=severity,  # type: ignore[arg-type]
            title=str(item.get("title") or "AI semantic review finding")[:120],
            evidence=str(item.get("evidence") or "AI judge identified this as a judgment-heavy item for human confirmation.")[:400],
            recommendation=str(item.get("recommendation") or "Review this item manually before accepting.")[:400],
            confidence=0.55,
            status="pending",
        ))
    return issues
