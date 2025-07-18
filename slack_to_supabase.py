import os
import time
import openai
import requests
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SLACK_API_BASE = "https://slack.com/api"
HEADERS = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}

# OpenAIで埋め込みベクトルを取得
def get_embedding(text):
    response = openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response["data"][0]["embedding"]

def get_channels():
    url = f"{SLACK_API_BASE}/conversations.list"
    params = {"exclude_archived": True, "limit": 1000}
    resp = requests.get(url, headers=HEADERS, params=params)
    return resp.json().get("channels", [])

def get_messages(channel_id, latest=None):
    url = f"{SLACK_API_BASE}/conversations.history"
    params = {"channel": channel_id, "limit": 1000}
    if latest:
        params["oldest"] = latest
    resp = requests.get(url, headers=HEADERS, params=params)
    return resp.json().get("messages", [])

def message_exists(ts):
    res = supabase.table("slack_messages").select("id").eq("timestamp", datetime.fromtimestamp(float(ts.split('.')[0])).isoformat()).execute()
    return len(res.data) > 0

def main():
    channels = get_channels()
    for ch in channels:
        channel_id = ch["id"]
        print(f"[INFO] チャンネル: {ch['name']} ({channel_id})")
        messages = get_messages(channel_id)
        for msg in messages:
            if msg.get("type") != "message" or "text" not in msg:
                continue
            ts = msg.get("ts")
            if message_exists(ts):
                continue
            text = msg["text"]
            user_id = msg.get("user")
            dt = datetime.fromtimestamp(float(ts.split('.')[0])) if ts else None
            embedding = get_embedding(text)
            data = {
                "message_text": text,
                "user_id": user_id,
                "timestamp": dt.isoformat() if dt else None,
                "embedding": embedding,
                "raw_json": msg
            }
            supabase.table("slack_messages").insert(data).execute()
            print(f"[INFO] 追加: {text[:30]}...")
            time.sleep(0.5)  # OpenAI APIのレート制限対策

if __name__ == "__main__":
    main() 