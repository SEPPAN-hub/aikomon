import os
import openai
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from supabase import create_client, Client
import numpy as np

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = App(token=SLACK_BOT_TOKEN)

# OpenAIで埋め込みベクトルを取得
def get_embedding(text):
    response = openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response["data"][0]["embedding"]

# Supabaseでベクトル検索
def search_similar_message(query_embedding, top_k=1):
    res = supabase.table("slack_messages").select("id, message_text, user_id, embedding").execute()
    messages = res.data
    if not messages:
        return None
    def cosine_similarity(a, b):
        a = np.array(a)
        b = np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    for m in messages:
        m["similarity"] = cosine_similarity(query_embedding, m["embedding"])
    messages = sorted(messages, key=lambda x: x["similarity"], reverse=True)
    return messages[:top_k]

@app.event("app_mention")
def handle_mention(event, say):
    user = event["user"]
    text = event["text"]
    cleaned_text = text.split(' ', 1)[-1] if ' ' in text else text
    query_embedding = get_embedding(cleaned_text)
    results = search_similar_message(query_embedding, top_k=1)
    if results and len(results) > 0:
        answer = results[0]["message_text"]
        say(f"<@{user}> さん、参考になりそうな過去メッセージはこちら：\n{answer}")
    else:
        say(f"<@{user}> さん、該当する情報が見つかりませんでした。")

if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start() 