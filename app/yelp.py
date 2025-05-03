import requests
from .config import YELP_API_KEY

headers = {"Authorization": f"Bearer {YELP_API_KEY}"}

def search_yelp(q: dict, limit=5):
    """
    q: {'categories': 'sushi', 'location': 'San Francisco', 'rating': 4}
    rating 只能在本地过滤，Yelp API 不支持 >=rating。
    """
    params = {
        "term": q.get("categories", "restaurant"),
        "location": q.get("location", "Los Angeles"),
        "limit": limit,
        "sort_by": "rating"
    }
    r = requests.get("https://api.yelp.com/v3/businesses/search",
                     headers=headers, params=params, timeout=10)
    r.raise_for_status()
    print("🌐 Yelp API Request Params:", params)
    print("📦 Yelp API Raw Response:", r.json())
    return r.json().get("businesses", [])
