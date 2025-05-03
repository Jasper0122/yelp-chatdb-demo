from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)
import os, pathlib

env_path = pathlib.Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

YELP_API_KEY = os.getenv("YELP_API_KEY")
MONGO_URI    = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


print("OPENAI_API_KEY in environment variables：", os.environ.get("OPENAI_API_KEY"))
print("✅ YELP_API_KEY =", YELP_API_KEY)
print("✅ OPENAI_API_KEY =", OPENAI_API_KEY)
print("✅ MONGO_URI =", MONGO_URI)
