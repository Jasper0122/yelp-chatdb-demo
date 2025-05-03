from pymongo import MongoClient, ASCENDING
from .config import MONGO_URI

client = MongoClient(MONGO_URI)
db = client["yelp_cache_db"]

# ---------- Collections ----------

# 1. Main restaurant data (cached Yelp results)
coll = db["restaurants"]
coll.create_index([("location", ASCENDING)])
coll.create_index([("categories", ASCENDING)])
coll.create_index([("rating", ASCENDING)])

# 2. User wishlist
wishlist_coll = db["wishlists"]
wishlist_coll.create_index("restaurant_name")

# 3. Conversation history (natural language requests, recommendations, follow-ups, etc.)
conversations_coll = db["conversations"]
conversations_coll.create_index("timestamp")
