import os
import json
import numpy as np
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import traceback
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境変数ロード
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

# 事前チェック
if not SUPABASE_URL or not SUPABASE_KEY or not OPENAI_API_KEY or not SLACK_BOT_TOKEN:
    raise ValueError("環境変数(SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY, SLACK_BOT_TOKEN)が不足しています")

# クライアント初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# Slack Bolt/Flask
app = App(token=SLACK_BOT_TOKEN)
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# ベクトル次元数
EMBEDDING_DIM = 1536

# embedding生成
def get_embedding(text):
    try:
        response = openai_client.embeddings.create(
            input=[text],
            model="text-embedding-3-small"
        )
        emb = response.data[0].embedding
        if len(emb) != EMBEDDING_DIM:
            logger.error(f"embedding次元数不一致: {len(emb)}")
            return None
        return emb
    except Exception as e:
        logger.error(f"OpenAI埋め込み生成失敗: {e}")
        return None

# Supabaseベクトル類似検索
def search_similar_messages(query_embedding, top_k=3):
    try:
        # 直接的なクエリでベクトル検索
        res = supabase.table("slack_messages").select("message_text, user_id, timestamp, embedding, raw_json").execute()
        
        if not res.data:
            logger.warning("データベースにメッセージがありません")
            return []
        
        # Pythonでコサイン類似度を計算
        def cosine_similarity(a, b):
            a = np.array(a, dtype=float)
            b = np.array(b, dtype=float)
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        
        # 各メッセージの類似度を計算
        messages_with_similarity = []
        for msg in res.data:
            if msg.get('embedding'):
                try:
                    # embeddingが文字列の場合はJSONとしてパース
                    if isinstance(msg['embedding'], str):
                        embedding = json.loads(msg['embedding'])
                    else:
                        embedding = msg['embedding']
                    
                    # 数値配列に変換
                    embedding = [float(x) for x in embedding]
                    
                    similarity = cosine_similarity(query_embedding, embedding)
                    messages_with_similarity.append({
                        **msg,
                        'similarity': similarity
                    })
                except Exception as e:
                    logger.error(f"embedding処理エラー: {e}")
                    continue
        
        # 類似度でソート
        messages_with_similarity.sort(key=lambda x: x['similarity'], reverse=True)
        
        # 上位k件を返す
        return messages_with_similarity[:top_k]
        
    except Exception as e:
        logger.error(f"Supabaseベクトル検索失敗: {e}")
        return []

# 要約・回答生成
def generate_answer(user_query, similar_messages):
    try:
        if not similar_messages:
            return "類似する過去メッセージが見つかりませんでした。"
        
        context = "\n".join([f"・{msg['message_text']}" for msg in similar_messages])
        prompt = f"""
あなたはSlackの社内AIアシスタントです。
以下の過去メッセージを参考に、ユーザーの質問に要約・生成して日本語で丁寧に答えてください。

[過去メッセージ]
{context}

[質問]
{user_query}

[回答]
"""
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.7
        )
        if response.choices and response.choices[0].message and response.choices[0].message.content:
            return response.choices[0].message.content.strip()
        else:
            logger.error("OpenAIレスポンスが不正です")
            return "要約生成中にエラーが発生しました。"
    except Exception as e:
        logger.error(f"OpenAI要約生成失敗: {e}")
        return "要約生成中にエラーが発生しました。"

# Slackメンションイベント
@app.event("app_mention")
def handle_mention(event, say):
    try:
        user = event["user"]
        text = event["text"]
        channel = event["channel"]
        logger.info(f"メンション受信: user={user}, text={text}")

        # embedding生成
        embedding = get_embedding(text)
        if embedding is None:
            say(f"<@{user}> embedding生成に失敗しました")
            return

        # 類似検索
        similar_messages = search_similar_messages(embedding, top_k=3)
        if not similar_messages:
            say(f"<@{user}> 類似する過去メッセージが見つかりませんでした")
            return

        # 要約・生成
        answer = generate_answer(text, similar_messages)
        say(f"<@{user}> {answer}")
    except Exception as e:
        logger.error(f"メンション処理失敗: {e}\n{traceback.format_exc()}")
        say(f"エラーが発生しました: {e}")

# Slackイベントエンドポイント
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    if request.json and "challenge" in request.json:
        return jsonify({"challenge": request.json["challenge"]})
    return handler.handle(request)

if __name__ == "__main__":
    flask_app.run(port=3000)
