# ── app/nlp.py  (revised) ──
"""LLM‑based intent classification & NL parsing utilities."""

from __future__ import annotations

import json
import re

from openai import OpenAI

from .cache_utils import load_from_cache, save_to_cache
from .config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

# ───────────────────────── intent classification ──────────────────────────

def _regex_intent(text: str) -> str | None:
    """Fast path: rule‑based intent detection (case‑insensitive)."""
    t = text.lower()
    if re.search(r"\b(add|save|remember|put)\b.*\b(wishlist|my ?list|saved)\b", t):
        return "wishlist_add"
    if re.search(r"\b(delete|remove|take off)\b.*\b(wishlist|my ?list|saved)\b", t):
        return "wishlist_delete"
    if re.search(r"\bupdate\b.*\bnote\b", t):
        return "wishlist_update"
    if re.search(r"\b(what|show|view)\b.*\b(wishlist|saved)\b", t):
        return "wishlist_view"
    if re.fullmatch(r"(hi+|hello+|hey+|yo+|sup)\b.*", t):
        return "smalltalk"
    return None

def classify_query_type(text: str) -> str:
    """Return the high‑level intent for *text* (uses cache → regex → GPT)."""
    cached = load_from_cache(text)
    if cached:
        return cached["intent"]

    intent = _regex_intent(text)
    if intent:
        save_to_cache(text, text, "matched_by_regex", intent)
        return intent

    prompt = (
        "You are an intent classifier.\n"
        "Your task is to rewrite a user's freeform input into a clean, standardized command,\n"
        "and classify what the user wants to do.\n\n"
        "Output ONLY valid JSON in this format:\n"
        "{ \"canonical\": string, \"intent\": string, \"analysis\": string }\n\n"
        "Intent options include:\n"
        "- wishlist_add (add/save restaurant to wishlist)\n"
        "- wishlist_delete (remove from wishlist)\n"
        "- wishlist_update (update wishlist note)\n"
        "- wishlist_view (view list of saved restaurants)\n"
        "- search (search for restaurants based on location/cuisine/etc)\n"
        "- chat_history (user wants to see conversation history)\n"
        "- smalltalk (greeting, hello, etc)\n"
        "- clarification (user is unclear or missing required info)\n\n"
        "DO NOT invent your own intent labels.\n"
        "Avoid these common mistakes:\n"
        "- Do not output 'command' or 'query' as intent.\n"
        "- Do not return extra text. ONLY valid JSON.\n"
        "- If the intent is ambiguous, fall back to 'clarification'.\n\n"
        f"User: \"{text}\""
    )

    resp = client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )

    obj = json.loads(resp.choices[0].message.content)
    canonical = obj["canonical"]
    intent = obj["intent"]
    analysis = obj.get("analysis", "")

    save_to_cache(text, canonical, analysis, intent)
    return intent

# ─────────────────────────── name extraction ─────────────────────────────

def extract_name_from_canonical(canonical: str) -> str:
    # 宽松提取餐厅名（匹配各种表达方式）
    match = re.search(
        r"(add|save|remember|remove|delete|forget|update)\s+(.*?)\s+(to|from)\s+(my\s+)?(wishlist|list|saved list)",
        canonical, re.I,
    )
    if match:
        name = match.group(2).strip()
        # 删除尾部 like "in New York"
        name = re.sub(r"\s+in\s+[\w\s]+$", "", name, flags=re.I)
        return name.strip()

    # fallback，简单粗暴删尾
    name = re.sub(r"(to|from)\s+(my\s+)?(wishlist|list|saved list)", "", canonical, flags=re.I)
    name = re.sub(r"^(add|save|remove|delete|update|remember)\s+", "", name, flags=re.I)
    name = re.sub(r"\s+in\s+[\w\s]+$", "", name, flags=re.I)
    return name.strip()


# ─────────────────── NL → structured search‑field extraction ──────────────

SYSTEM_PROMPT = """
You are a helpful restaurant search assistant. Your task is to extract structured information in JSON format from a user's natural language query.

Return a JSON object with the following fields:
- location (city)
- categories (e.g., pizza, sushi) [optional]
- rating (minimum rating, e.g., 4) [optional]
- price (e.g., $, $$, $$$) [optional]

If the user says vague things like \"near me\" or \"current location\", default to \"Los Angeles\".

Respond ONLY with a valid JSON object. No explanations.
"""

def parse_nl_query(text: str) -> dict:
    """Parse *text* into structured search fields using GPT."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]

    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        parsed = json.loads(resp.choices[0].message.content)

        missing = []
        if not parsed.get("location"):
            missing.append("location")
        if not parsed.get("categories"):
            missing.append("categories")

        followup = ""
        if missing:
            followup_prompt = (
                f'The user said: "{text}"\n'
                f'We extracted this: {json.dumps(parsed)}\n'
                f'The following fields are missing: {", ".join(missing)}.\n\n'
                "Please generate a friendly English follow‑up question to ask for the missing information. "
                "Output only the question."
            )
            followup_resp = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a friendly restaurant assistant."},
                    {"role": "user", "content": followup_prompt},
                ],
                temperature=0.7,
                max_tokens=100,
            )
            followup = followup_resp.choices[0].message.content.strip()

        return {
            "parsed": parsed,
            "missing": missing,
            "followup": followup,
            "original": text,
        }

    except Exception as e:
        print("Parse failed:", e)
        return {
            "parsed": {},
            "missing": ["location", "categories"],
            "followup": "Sorry, I couldn’t understand. Could you tell me which city and cuisine you're looking for?",
            "original": text,
        }