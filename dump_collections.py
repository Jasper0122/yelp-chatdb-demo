import json
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from pathlib import Path

# ==== MongoDB 配置 ====
client = MongoClient("mongodb://localhost:27017/")
db = client["yelp_cache_db"]

# ==== 输出设置 ====
output_dir = Path(__file__).parent
collections = ["restaurants", "wishlists", "conversations"]

# ==== 递归转换 ObjectId 和 datetime ====
def sanitize(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(i) for i in obj]
    return obj

# ==== 导出为 JSON 文件 ====
def export_to_json(collection_name):
    data = [sanitize(doc) for doc in db[collection_name].find()]
    output_file = output_dir / f"{collection_name}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Exported {len(data)} documents to {output_file.name}")

# ==== 执行导出 ====
for name in collections:
    export_to_json(name)
