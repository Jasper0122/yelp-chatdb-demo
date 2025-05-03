"""
Wishlist logic: Reference the restaurants collection and support candidate list confirmation.
"""
from datetime import datetime
import re
from typing import List, Dict
from fastapi import APIRouter

from bson import ObjectId
from .db import coll as rest_coll, wishlist_coll          # restaurants, wishlists
from .yelp import search_yelp

router = APIRouter()

# ──────────────────────────────────────────────
# Internal tool
# ──────────────────────────────────────────────
def _search_candidates(name: str, location="Los Angeles") -> List[Dict]:
    """
    ① First, use regex to find up to 5 entries in the local restaurants collection.
    ② If fewer than 5 are found, call the Yelp API for an exact search, write the results to the local database, and return them.
    """
    regex = {"$regex": f"{re.escape(name)}", "$options": "i"}
    docs  = list(rest_coll.find({"name": regex}).limit(5))
    if docs:
        return docs

    biz = search_yelp({"categories": name, "location": location}, limit=5)
    for b in biz:
        doc = {
            "yelp_id": b["id"],
            "name": b["name"],
            "address": ", ".join(b["location"]["display_address"]),
            "img": b.get("image_url", ""),
            "rating": b.get("rating"),
            "url": b.get("url", ""),
        }
        rest_coll.update_one({"yelp_id": b["id"]}, {"$setOnInsert": doc}, upsert=True)
        docs.append(rest_coll.find_one({"yelp_id": b["id"]}))
    return docs


# ──────────────────────────────────────────────
# Public functions (called by main.py)
# ──────────────────────────────────────────────
def add_to_wishlist(restaurant_name: str, note: str = "", user_id="default", cand_id: str = None):
    if cand_id:
        r = rest_coll.find_one({"_id": ObjectId(cand_id)})
        if not r:
            return f"❌ Candidate not found."
        if wishlist_coll.find_one({"user_id": user_id, "restaurant_id": r["_id"]}):
            return f"⚠️ **{r['name']}** is already in your wishlist."
        wishlist_coll.insert_one({
            "user_id": user_id,
            "restaurant_id": r["_id"],
            "restaurant_name": r["name"],
            "note": note,
            "added_at": datetime.utcnow(),
        })
        return f"✅ **{r['name']}** has been added to your wishlist."

    cands = _search_candidates(restaurant_name)
    if len(cands) == 1:
        r = cands[0]
        return add_to_wishlist(restaurant_name, note, user_id, str(r["_id"]))

    follow = f"I found these matches for **{restaurant_name}**. Which one did you mean?\n\n"
    for i, r in enumerate(cands, 1):
        follow += (
            f"{i}. **<a href='#' data-cand='{r['_id']}' class='cand-link'>{r['name']}</a>**"
            f" – {r.get('address','')}\n"
        )
    return {"status": "ambiguous", "followup": follow, "candidates": cands}



def delete_from_wishlist(restaurant_name: str, user_id="default"):
    regex = {"$regex": f"{re.escape(restaurant_name)}", "$options": "i"}
    rest  = rest_coll.find_one({"name": regex})
    if not rest:
        return f"⚠️ I couldn’t find **{restaurant_name}**."
    res = wishlist_coll.delete_one({"user_id": user_id, "restaurant_id": rest["_id"]})
    if res.deleted_count:
        return f"❌ **{rest['name']}** has been removed from your wishlist."
    return f"⚠️ **{rest['name']}** was not in your wishlist."


def update_note(restaurant_name: str, new_note: str, user_id="default"):
    regex = {"$regex": f"{re.escape(restaurant_name)}", "$options": "i"}
    rest  = rest_coll.find_one({"name": regex})
    if not rest:
        return f"⚠️ I couldn’t find **{restaurant_name}**."
    res = wishlist_coll.update_one(
        {"user_id": user_id, "restaurant_id": rest["_id"]},
        {"$set": {"note": new_note}},
    )
    if res.matched_count == 0:
        return f"⚠️ **{rest['name']}** is not in your wishlist."
    return f"📝 Note for **{rest['name']}** updated to: {new_note}"


def get_wishlist(user_id="default") -> str:
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$lookup": {
                "from": "restaurants",
                "localField": "restaurant_id",
                "foreignField": "_id",
                "as": "rest",
            }
        },
        {"$unwind": "$rest"},
        {"$sort": {"added_at": -1}},
    ]
    items = list(wishlist_coll.aggregate(pipeline))
    if not items:
        return "📭 Your wishlist is currently empty."
    resp = "📌 **Here’s your wishlist:**\n\n"
    for i, it in enumerate(items, 1):
        rid = str(it["rest"]["_id"])
        resp += (
            f"{i}. **<a href='#' data-id='{rid}' class='wish-link'>{it['rest']['name']}</a>**"
        )
        if it.get("note"):
            resp += f" – _{it['note']}_"
        resp += "\n"
    return resp.strip()


# ──────────────────────────────────────────────
# API endpoints (used by frontend buttons/links)
# ──────────────────────────────────────────────
@router.get("/wishlist")
def view_wishlist():
    return get_wishlist()
