# ───────────────────────── app/main.py ─────────────────────────
"""FastAPI backend for the Yelp ChatDB demo (completed version)."""

from __future__ import annotations

import datetime
import re
import uuid

from bson import ObjectId
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from openai import OpenAI

from .cache_utils import load_from_cache
from .config import OPENAI_API_KEY
from .db import coll, conversations_coll, wishlist_coll
from .nlp import (
    classify_query_type,
    extract_name_from_canonical,
    parse_nl_query,
)
from .yelp import search_yelp

app = FastAPI(title="Yelp ChatDB Demo")
client = OpenAI(api_key=OPENAI_API_KEY)

# ─────────────────────────── CORS -----------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────── Utils ----------------------------------------

def _sanitize(obj):
    """Recursively drop Mongo `_id` objects or convert them to str for JSON."""
    from collections.abc import Mapping, Sequence

    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, Mapping):
        return {k: _sanitize(v) for k, v in obj.items() if k != "_id"}
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        return [_sanitize(i) for i in obj]
    return obj


def gpt_summary(results):
    if not results:
        return "Sorry, I couldn't find any matching restaurants."  # noqa: E501
    lines = "".join(f"- {r['name']} ({r['rating']}★) at {r['address']}\n" for r in results)
    prompt = (
        "Write a short friendly recommendation based on these restaurants:\n\n"
        + lines
    )
    out = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful restaurant guide."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=120,
    )
    return out.choices[0].message.content.strip()


def extract_wishlist_note(text: str) -> str:
    """Pull the note portion from text like `... to say "best ramen"`."""
    m = re.search(r"to say ['\"](.+?)['\"]", text, re.I)
    return m.group(1) if m else ""


def _log(session_id, user_text, resp, parsed, intent, results=None):
    conversations_coll.insert_one(
        {
            "session_id": session_id,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "user_input": user_text,
            "response": _sanitize(resp),
            "intent": intent,
            "parsed": _sanitize(parsed),
            "results": _sanitize(results),
        }
    )

# ─────────────────────────── Routes ---------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    with open("frontend.html", "r", encoding="utf-8") as fh:
        return fh.read()


@app.post("/search")
async def search(payload: dict, request: Request):
    print("Incoming payload:", payload)
    user_text = str(payload.get("query", "")).strip()
    session_id = payload.get("session_id") or str(uuid.uuid4())
    if not user_text:
        raise HTTPException(400, "query required")

    intent = classify_query_type(user_text)

    # Early return for non-search intents
    if intent == "chat_history":
        logs = conversations_coll.find({"session_id": session_id}).sort("timestamp", -1).limit(10)
        history = [
            f"<li><b>{doc['user_input']}</b>: {doc.get('response', '')[:120]}...</li>"
            for doc in logs if doc.get("response")
        ]
        return {"status": "history", "msg": "<ul>" + "\n".join(history[::-1]) + "</ul>"}

    if intent == "smalltalk":
        return {"status": "chat", "msg": "👋 Hi there! How can I help you with food today?"}

    if intent == "wishlist_view":
        return {"status": "wishlist", "msg": _render_wishlist()}

    if intent.startswith("wishlist"):
        cache_hit = load_from_cache(user_text)
        canonical = cache_hit["canonical"] if cache_hit else user_text
        name = extract_name_from_canonical(canonical)
        note = extract_wishlist_note(user_text)

        parsed = {}
        last = conversations_coll.find_one(
            {"session_id": session_id, "parsed.location": {"$exists": True}},
            sort=[("timestamp", -1)],
        )
        if last:
            parsed["location"] = last["parsed"].get("location")

        if intent == "wishlist_add":
            return _wishlist_add(session_id, name, note, parsed, user_text)
        elif intent == "wishlist_delete":
            msg = _wishlist_delete(name)
        elif intent == "wishlist_update":
            msg = _wishlist_update_note(name, note)
        else:
            msg = "Sorry, I didn't understand."
        _log(session_id, user_text, msg, parsed, intent)
        return {"status": "wishlist", "msg": msg}

    # search intent
    p_res = parse_nl_query(user_text)
    print("Parsed GPT Output:", p_res)
    parsed, missing, followup = p_res["parsed"], p_res["missing"], p_res["followup"]

    # Context inheritance
    last = conversations_coll.find_one(
        {"session_id": session_id, "parsed.location": {"$exists": True}},
        sort=[("timestamp", -1)],
    )
    if last:
        for k in ("location", "categories", "rating", "price"):
            parsed.setdefault(k, last["parsed"].get(k))
        missing = [k for k in ("location", "categories") if not parsed.get(k)]

    if missing:
        _log(session_id, user_text, followup, parsed, "clarification")
        return {"status": "incomplete", "followup": followup}

    # Query local MongoDB
    docs = list(
        coll.find({"location": parsed.get("location"), "categories": parsed.get("categories")}).limit(5)
    )
    print("MongoDB Query:", {"location": parsed.get("location"), "categories": parsed.get("categories")})
    print("MongoDB Results:", docs)
    if docs:
        for d in docs:
            d["_id"] = str(d["_id"])
            d.setdefault("img", "https://via.placeholder.com/400x200?text=No+Image")
            d.setdefault("url", "https://www.yelp.com")
        summary = gpt_summary(docs)
        _log(session_id, user_text, summary, parsed, "search", docs)
        return {"status": "complete", "source": "mongo", "summary": summary, "results": docs}

    # Yelp fallback
    yelp = search_yelp(parsed)
    if not yelp:
        return {"status": "complete", "summary": "No results found.", "results": []}

    cleaned: list[dict] = []
    for biz in yelp:
        doc = {
            "yelp_id": biz["id"],
            "name": biz["name"],
            "categories": parsed.get("categories"),
            "location": parsed.get("location"),
            "rating": biz.get("rating"),
            "price": biz.get("price"),
            "address": ", ".join(biz["location"]["display_address"]),
            "img": biz.get("image_url", ""),
            "url": biz.get("url", ""),
            "lat": biz["coordinates"]["latitude"],
            "lng": biz["coordinates"]["longitude"],
        }
        coll.update_one({"yelp_id": biz["id"]}, {"$set": doc}, upsert=True)
        stored = coll.find_one({"yelp_id": biz["id"]})
        if not stored:
            continue
        cleaned.append(
            {
                "_id": str(stored["_id"]),
                "name": doc["name"],
                "rating": doc.get("rating"),
                "address": doc.get("address"),
                "price": doc.get("price"),
                "img": doc["img"] or "https://via.placeholder.com/400x200?text=No+Image",
                "url": doc["url"] or "https://www.yelp.com",
                "lat": doc["lat"],
                "lng": doc["lng"],
            }
        )

    summary = gpt_summary(cleaned)
    _log(session_id, user_text, summary, parsed, "search", cleaned)
    return {"status": "complete", "summary": summary, "results": cleaned}


# ─────────────────── Wishlist helper funcs & routes -----------------------

def _render_wishlist() -> str:
    items = list(wishlist_coll.find({}))
    if not items:
        return "<i>📭 Your wishlist is currently empty.</i>"
    html_parts: list[str] = []
    for it in items:
        r = coll.find_one({"_id": it["restaurant_id"]})
        if not r:
            continue
        html_parts.append(
            f"<div class='wishlist-item' data-id='{str(r['_id'])}'>"
            f"<img src='{r.get('img', 'https://via.placeholder.com/48')}' style='width:48px;height:48px;border-radius:6px;object-fit:cover;' />"
            f"<a href='#' data-id='{str(r['_id'])}' class='wish-link'>{r['name']}</a>"
            f"<button class='remove-btn' data-id='{str(r['_id'])}'>❌</button>"
            "</div>"
        )
    return "\n".join(html_parts)


def _wishlist_add(sess, name: str, note: str, parsed, user_input):
    rest = coll.find_one({"name": {"$regex": name, "$options": "i"}})
    if not rest:
        msg = f"⚠️ Can't find restaurant named **{name}**."
        _log(sess, user_input, msg, parsed, "wishlist_add")
        return {"status": "wishlist", "msg": msg}

    if wishlist_coll.find_one({"restaurant_id": rest["_id"]}):
        return {
            "status": "wishlist",
            "msg": f"⚠️ {rest['name']} is already in your wishlist."
        }

    wishlist_coll.insert_one(
        {
            "restaurant_id": rest["_id"],
            "restaurant_name": rest["name"],
            "note": note,
            "added_at": datetime.datetime.utcnow(),
        }
    )
    return {
        "status": "wishlist",
        "msg": f"✅ {rest['name']} has been added to your wishlist."
    }


def _wishlist_delete(name: str) -> str:
    rest = coll.find_one({"name": {"$regex": name, "$options": "i"}})
    if not rest:
        return f"⚠️ Cannot find restaurant named {name} from wishlist."
    res = wishlist_coll.delete_one({"restaurant_id": rest["_id"]})
    return "✅ Removed." if res.deleted_count else "⚠️ Not found in wishlist."


def _wishlist_update_note(name: str, note: str) -> str:
    rest = coll.find_one({"name": {"$regex": name, "$options": "i"}})
    if not rest:
        return f"⚠️ Cannot find restaurant named {name}."
    upd = wishlist_coll.update_one(
        {"restaurant_id": rest["_id"]},
        {"$set": {"note": note, "updated_at": datetime.datetime.utcnow()}},
    )
    return "✅ Note updated." if upd.modified_count else "⚠️ No existing item to update."

# -- separate API endpoints for wishlist panel actions --------------------

@app.get("/wishlist", response_class=HTMLResponse)
def wishlist_html():
    return _render_wishlist()


@app.post("/wishlist/confirm/{rid}")
def wishlist_confirm(rid: str):
    try:
        obj = ObjectId(rid)
    except Exception:
        return {"msg": "Invalid restaurant ID."}
    rest = coll.find_one({"_id": obj})
    if not rest:
        return {"msg": "Restaurant not found."}
    if wishlist_coll.find_one({"restaurant_id": obj}):
        return {"msg": f"{rest['name']} is already in your wishlist."}
    wishlist_coll.insert_one(
        {"restaurant_id": obj, "restaurant_name": rest["name"], "added_at": datetime.datetime.utcnow()}
    )
    return {"msg": f"{rest['name']} added to wishlist."}