import os
import json
import numpy as np
from typing import List, Dict, Any
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
from datetime import datetime, timedelta

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境変数ロード
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# 事前チェック
if not SUPABASE_URL or not SUPABASE_KEY or not OPENAI_API_KEY or not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise ValueError("環境変数(SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY, SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET)が不足しています")

# クライアント初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# Slack Bolt/Flask
app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# ベクトル次元数
EMBEDDING_DIM = 1536

# 会話履歴を保持する辞書（メモリ内）
conversation_history = {}

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

# 改良されたSupabaseベクトル類似検索
def search_similar_messages(query_embedding, top_k=5, min_similarity=0.3):
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
                    
                    # 類似度が閾値を超える場合のみ追加
                    if similarity >= min_similarity:
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

# 改良された要約・回答生成（会話履歴対応）
def generate_answer(user_query, similar_messages, conversation_key=None):
    try:
        # 会話履歴を取得
        history = conversation_history.get(conversation_key, []) if conversation_key else []
        
        # 類似メッセージの詳細情報を構築
        context_parts = []
        if similar_messages:
            for i, msg in enumerate(similar_messages, 1):
                similarity = msg.get('similarity', 0)
                context_parts.append(f"{i}. 類似度: {similarity:.3f} - {msg['message_text']}")
        
        context = "\n".join(context_parts) if context_parts else "関連する過去メッセージが見つかりませんでした。"
        
        # 会話履歴を含むプロンプト構築
        system_prompt = """あなたはSlackの社内AIアシスタント「Mr.Vector」です。
以下の過去メッセージを参考に、ユーザーの質問に日本語で丁寧に答えてください。
会話の文脈を理解し、自然な会話を心がけてください。"""

        messages = [{"role": "system", "content": system_prompt}]
        
        # 会話履歴を追加
        for hist in history[-5:]:  # 最新5件の履歴のみ使用
            if hist["role"] in ["user", "assistant"]:
                messages.append({"role": hist["role"], "content": hist["content"]})
        
        # 現在の質問とコンテキスト
        user_content = f"""以下の過去メッセージを参考に質問に答えてください：

[参考メッセージ]
{context}

[質問]
{user_query}

回答は自然で親しみやすい日本語で、Mr.Vectorとして回答してください。"""
        
        messages.append({"role": "user", "content": user_content})
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=800,
            temperature=0.7
        )
        
        if response.choices and response.choices[0].message and response.choices[0].message.content:
            answer = response.choices[0].message.content.strip()
            
            # 会話履歴に追加
            if conversation_key:
                if conversation_key not in conversation_history:
                    conversation_history[conversation_key] = []
                
                conversation_history[conversation_key].append({
                    "role": "user",
                    "content": user_query,
                    "timestamp": datetime.now()
                })
                conversation_history[conversation_key].append({
                    "role": "assistant",
                    "content": answer,
                    "timestamp": datetime.now()
                })
                
                # 履歴が長すぎる場合は古いものを削除
                if len(conversation_history[conversation_key]) > 20:
                    conversation_history[conversation_key] = conversation_history[conversation_key][-10:]
            
            return answer
        else:
            logger.error("OpenAIレスポンスが不正です")
            return "回答生成中にエラーが発生しました。"
    except Exception as e:
        logger.error(f"OpenAI要約生成失敗: {e}")
        return "回答生成中にエラーが発生しました。"

# 改良されたSlackメンションイベント
@app.event("app_mention")
def handle_mention(event, say):
    try:
        user = event["user"]
        text = event["text"]
        channel = event["channel"]
        thread_ts = event.get("thread_ts") or event.get("ts")  # スレッド内かどうか判定
        logger.info(f"メンション受信: user={user}, text={text}, thread_ts={thread_ts}")

        # 会話キーを生成（チャンネル+スレッド）
        conversation_key = f"{channel}_{thread_ts}"

        # embedding生成
        embedding = get_embedding(text)
        if embedding is None:
            # スレッド内で返信
            slack_client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text="embedding生成に失敗しました。"
            )
            return

        # 類似検索（精度向上のため上位5件、類似度0.3以上）
        similar_messages = search_similar_messages(embedding, top_k=5, min_similarity=0.3)
        
        # 要約・生成
        answer = generate_answer(text, similar_messages, conversation_key)
        
        # スレッド内で返信（Mr.Vectorとして）
        slack_client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=answer,
            username="Mr.Vector",  # 表示名をMr.Vectorに設定
            icon_emoji=":robot_face:"  # ロボットアイコン
        )
        
    except Exception as e:
        logger.error(f"メンション処理失敗: {e}\n{traceback.format_exc()}")
        try:
            slack_client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"エラーが発生しました: {e}",
                username="Mr.Vector",
                icon_emoji=":robot_face:"
            )
        except:
            pass

# ヘルスチェックエンドポイント
@flask_app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Slack AI Bot is running"})

# Slackイベントエンドポイント
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    logger.info(f"Slackイベント受信: {request.json}")
    if request.json and "challenge" in request.json:
        challenge = request.json["challenge"]
        logger.info(f"URL検証チャレンジ: {challenge}")
        return jsonify({"challenge": challenge})
    return handler.handle(request)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port)
