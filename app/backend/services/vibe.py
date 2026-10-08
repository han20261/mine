"""Service layer that turns natural language into a runnable single-file H5 app."""

import logging
import re

from fastapi import HTTPException
from schemas.aihub import ChatMessage, GenTxtRequest
from schemas.vibe import GenerateAppRequest, GenerateAppResponse
from services.aihub import AIHubService

logger = logging.getLogger(__name__)

GENERATOR_MODEL = "claude-opus-5"
MAX_HISTORY_TURNS = 8

SYSTEM_PROMPT = """You are a senior front-end engineer who ships tiny but complete H5 apps.

Deliverable rules:
- Return ONE self-contained HTML document: <!DOCTYPE html> ... inline <style> and inline <script>.
- No external network requests: no CDN, no external fonts, no remote images. Use inline SVG, CSS art or emoji instead.
- Mobile-first H5 layout: use a responsive viewport meta tag, flexible layout, and touch-friendly controls (min 40px tap targets).
- Everything must actually work: wire real interactions and state. Never leave dead buttons or TODO placeholders.
- If you persist data, wrap storage access so a blocked/opaque origin cannot break the app: `try { localStorage.setItem(...) } catch (e) {}` with an in-memory fallback.
- Keep the whole file under 700 lines, readable, with clear section comments.
- Use semantic markup and accessible labels.

Response format:
1. First line: TITLE: <a short app title in the user's language, max 20 characters>
2. Second line: SUMMARY: <one sentence, in the user's language, describing what you built or changed>
3. Then exactly one ```html fenced code block containing the complete document. Never truncate the code block.
"""


def _extract_html_block(text: str) -> str:
    """Pull the HTML document out of a model answer that may include prose or fences."""
    fenced = re.search(r"```(?:html)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1).strip() if fenced else text.strip()

    start = candidate.lower().find("<!doctype")
    if start == -1:
        start = candidate.lower().find("<html")
    if start > 0:
        candidate = candidate[start:]

    end = candidate.lower().rfind("</html>")
    if end != -1:
        candidate = candidate[: end + len("</html>")]

    return candidate.strip()


def _extract_meta_line(text: str, label: str) -> str:
    """Read a `LABEL: value` header line, tolerating markdown decorations."""
    match = re.search(rf"^\s*\**{label}\**\s*:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip().strip("*`# ") if match else ""


def _build_messages(payload: GenerateAppRequest) -> list[ChatMessage]:
    """Compose the instruction messages for create or edit mode."""
    messages: list[ChatMessage] = [ChatMessage(role="system", content=SYSTEM_PROMPT)]

    for turn in payload.history[-MAX_HISTORY_TURNS:]:
        messages.append(ChatMessage(role=turn.role, content=turn.content))

    if payload.mode == "edit" and payload.current_code:
        instruction = (
            "Here is the CURRENT app source. Apply the user's change request to it and return the FULL updated file.\n\n"
            f"```html\n{payload.current_code}\n```"
        )
        messages.append(ChatMessage(role="user", content=instruction))

    messages.append(ChatMessage(role="user", content=payload.prompt))
    return messages


async def generate_app(payload: GenerateAppRequest) -> GenerateAppResponse:
    """Generate or refine an H5 app and return validated source code."""
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Please describe the app you want to build.")

    if payload.mode == "edit" and not (payload.current_code or "").strip():
        raise HTTPException(status_code=400, detail="There is no current app to modify yet.")

    service = AIHubService()
    request = GenTxtRequest(
        messages=_build_messages(payload),
        model=GENERATOR_MODEL,
        stream=False,
        temperature=0.6,
        max_tokens=8192,
    )

    try:
        response = await service.gentxt(request)
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the client
        logger.error("vibe generation failed: %s", exc)
        raise HTTPException(status_code=502, detail="The generator is unavailable right now. Please retry.") from exc

    raw = response.content or ""
    code = _extract_html_block(raw)

    if "<" not in code or ">" not in code:
        logger.warning("vibe generation returned unusable output: %s", raw[:200])
        raise HTTPException(status_code=502, detail="The generator returned unreadable code. Please retry.")

    title = _extract_meta_line(raw, "TITLE") or (payload.app_name or "Untitled App")
    summary = _extract_meta_line(raw, "SUMMARY") or "App updated."

    return GenerateAppResponse(code=code, title=title[:40], summary=summary[:300], model=GENERATOR_MODEL)
