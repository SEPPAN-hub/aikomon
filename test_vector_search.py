import os
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI
import json
import numpy as np

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY or not OPENAI_API_KEY:
    raise ValueError("環境変数が不足しています")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def get_embedding(text):
    """テキストをベクトル化"""
    try:
        response = openai_client.embeddings.create(
            input=[text],
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ 埋め込み生成失敗: {e}")
        return None

def search_similar_messages(query_embedding, top_k=3):
    """Supabaseでベクトル類似検索"""
    try:
        # 直接的なクエリでベクトル検索
        res = supabase.table("slack_messages").select("message_text, user_id, timestamp, embedding, raw_json").execute()
        
        if not res.data:
            print("⚠️  データベースにメッセージがありません")
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
                    print(f"⚠️  embedding処理エラー: {e}")
                    continue
        
        # 類似度でソート
        messages_with_similarity.sort(key=lambda x: x['similarity'], reverse=True)
        
        # 上位k件を返す
        return messages_with_similarity[:top_k]
        
    except Exception as e:
        print(f"❌ ベクトル検索失敗: {e}")
        return []

def generate_answer(user_query, similar_messages):
    """類似メッセージを基に回答生成"""
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
            return "回答生成中にエラーが発生しました。"
    except Exception as e:
        print(f"❌ 回答生成失敗: {e}")
        return "回答生成中にエラーが発生しました。"

def test_vector_search():
    """ベクトル検索機能のテスト"""
    print("🔍 ベクトル検索機能テスト")
    print("=" * 50)
    
    # テスト用の質問
    test_questions = [
        "競馬の予想について教えて",
        "会社の移転について",
        "撮影の予定について",
        "オフィスの物件について",
        "AIについて"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n📝 テスト {i}: {question}")
        print("-" * 30)
        
        # 1. 質問文をベクトル化
        print("1. 質問文をベクトル化中...")
        embedding = get_embedding(question)
        if embedding is None:
            print("❌ ベクトル化失敗")
            continue
        print(f"✅ ベクトル化完了 (次元数: {len(embedding)})")
        
        # 2. 類似メッセージ検索
        print("2. 類似メッセージ検索中...")
        similar_messages = search_similar_messages(embedding, top_k=3)
        if not similar_messages:
            print("❌ 類似メッセージなし")
            continue
        print(f"✅ {len(similar_messages)}件の類似メッセージを発見")
        
        # 3. 類似メッセージを表示
        print("3. 類似メッセージ:")
        for j, msg in enumerate(similar_messages, 1):
            distance = msg.get('similarity', 'N/A')
            text = msg.get('message_text', 'N/A')[:100] + "..." if len(msg.get('message_text', '')) > 100 else msg.get('message_text', 'N/A')
            print(f"   {j}. 類似度: {distance:.4f}")
            print(f"      内容: {text}")
        
        # 4. 回答生成
        print("4. 回答生成中...")
        answer = generate_answer(question, similar_messages)
        print(f"✅ 回答: {answer}")
        
        print("-" * 50)

def interactive_test():
    """対話的なテスト"""
    print("\n🎯 対話的テストモード")
    print("質問を入力してください（'quit'で終了）")
    print("=" * 50)
    
    while True:
        question = input("\n質問: ").strip()
        if question.lower() in ['quit', 'exit', 'q']:
            break
        if not question:
            continue
        
        print(f"\n🔍 検索中: {question}")
        
        # ベクトル化
        embedding = get_embedding(question)
        if embedding is None:
            print("❌ ベクトル化失敗")
            continue
        
        # 類似検索
        similar_messages = search_similar_messages(embedding, top_k=3)
        if not similar_messages:
            print("❌ 類似メッセージなし")
            continue
        
        # 類似メッセージ表示
        print(f"\n📋 類似メッセージ ({len(similar_messages)}件):")
        for i, msg in enumerate(similar_messages, 1):
            distance = msg.get('similarity', 'N/A')
            text = msg.get('message_text', 'N/A')
            print(f"{i}. 類似度: {distance:.4f}")
            print(f"   内容: {text}")
            print()
        
        # 回答生成
        answer = generate_answer(question, similar_messages)
        print(f"🤖 回答: {answer}")

if __name__ == "__main__":
    print("ベクトル検索機能テスト")
    print("1. 自動テスト")
    print("2. 対話的テスト")
    
    choice = input("選択してください (1/2): ").strip()
    
    if choice == "1":
        test_vector_search()
    elif choice == "2":
        interactive_test()
    else:
        print("無効な選択です。自動テストを実行します。")
        test_vector_search() 