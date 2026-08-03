"""Prompt templates — pure string-building, no HTTP, so these are testable
without Ollama at all. See docs/AI_DESIGN.md §2-3 for the design rationale.

CLASSIFICATION_CATEGORIES/PRIORITIES are hardcoded rather than imported
from the backend's enums, deliberately — ai_engine/ has zero dependency on
`backend/`'s codebase (a separate uv project, a separate process). These
values must match docs/DATABASE.md §5's `complaint_category`/`priority`
enums exactly; that note lives in DATABASE.md too, since it constrains
both sides.
"""

import json

CLASSIFICATION_CATEGORIES = ["PLUMBING", "ELECTRICAL", "CLEANING", "WIFI", "FOOD", "SECURITY", "OTHER"]
CLASSIFICATION_PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"]


def classification_messages(description: str) -> list[dict]:
    system = (
        "You triage maintenance/service complaints for a PG (paying guest) accommodation. "
        "Given a tenant's complaint description, respond with ONLY a JSON object with exactly "
        'these three keys: "category" (one of ' + ", ".join(CLASSIFICATION_CATEGORIES) + "), "
        '"priority" (one of ' + ", ".join(CLASSIFICATION_PRIORITIES) + "), and "
        '"suggested_action" (a short, concrete next step for PG staff, one sentence). No other text.'
    )
    examples = [
        {"role": "user", "content": "The bathroom tap is leaking constantly."},
        {
            "role": "assistant",
            "content": json.dumps(
                {
                    "category": "PLUMBING",
                    "priority": "HIGH",
                    "suggested_action": "Send a plumber to replace the tap washer.",
                }
            ),
        },
        {"role": "user", "content": "Wifi has been slow for the last two days."},
        {
            "role": "assistant",
            "content": json.dumps(
                {
                    "category": "WIFI",
                    "priority": "MEDIUM",
                    "suggested_action": "Restart the router and check the ISP connection.",
                }
            ),
        },
    ]
    return [{"role": "system", "content": system}, *examples, {"role": "user", "content": description}]


def summary_messages(stats: dict) -> list[dict]:
    system = (
        "You write short, plain-language daily management summaries for a PG (paying guest) "
        "accommodation owner/manager, from JSON statistics. 3-5 sentences. Call out what needs "
        "attention (overdue rent, urgent complaints) rather than listing every number. Do not "
        "invent figures not present in the input."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(stats)}]


def answer_messages(question: str, context: list[dict]) -> list[dict]:
    context_text = "\n\n".join(f"[{c['source']}]\n{c['content']}" for c in context)
    system = (
        "Answer the tenant's question using ONLY the context below, drawn from the PG's own "
        "rules/policy documents. Each context section is labeled with its source file. If the "
        "context doesn't contain the answer, say you don't know rather than guessing. Be concise."
    )
    user = f"Context:\n{context_text}\n\nQuestion: {question}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
