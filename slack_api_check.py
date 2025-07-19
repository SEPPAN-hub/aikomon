import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import json

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

def check_slack_api():
    """Slack APIの状況を確認"""
    if not SLACK_BOT_TOKEN:
        print("❌ SLACK_BOT_TOKENが設定されていません")
        return False
    
    client = WebClient(token=SLACK_BOT_TOKEN)
    
    print("🔍 Slack API状況確認中...")
    print(f"Bot Token: {SLACK_BOT_TOKEN[:10]}...")
    
    try:
        # 1. 認証テスト
        print("\n1. 認証テスト")
        auth_response = client.auth_test()
        if not auth_response or not auth_response.get('ok'):
            print("❌ 認証失敗")
            return False
            
        print(f"✅ 認証成功")
        print(f"   - ワークスペース: {auth_response.get('team', 'N/A')}")
        print(f"   - ユーザーID: {auth_response.get('user_id', 'N/A')}")
        print(f"   - Bot名: {auth_response.get('user', 'N/A')}")
        
        # 2. Bot情報取得
        print("\n2. Bot情報")
        bot_id = auth_response.get('bot_id')
        if bot_id:
            try:
                bot_info = client.bots_info(bot=bot_id)
                if bot_info and bot_info.get('ok'):
                    print(f"✅ Bot情報取得成功")
                    bot_data = bot_info.get('bot', {})
                    print(f"   - Bot ID: {bot_data.get('id', 'N/A')}")
                    print(f"   - Bot名: {bot_data.get('name', 'N/A')}")
                else:
                    print("⚠️  Bot情報取得失敗")
            except SlackApiError as e:
                print(f"⚠️  Bot情報取得エラー: {e.response.get('error', 'Unknown error')}")
        else:
            print("⚠️  Bot IDが取得できませんでした")
        
        # 3. チャンネル一覧取得
        print("\n3. チャンネル一覧")
        try:
            channels_response = client.conversations_list(types="public_channel,private_channel")
            if channels_response and channels_response.get('ok'):
                channels = channels_response.get('channels', [])
                print(f"✅ チャンネル数: {len(channels)}")
                
                # Botが参加しているチャンネル
                bot_channels = [ch for ch in channels if ch.get('is_member', False)]
                print(f"   - Bot参加チャンネル数: {len(bot_channels)}")
                
                if bot_channels:
                    print("   - 参加チャンネル:")
                    for ch in bot_channels[:5]:  # 最初の5つを表示
                        print(f"     • #{ch.get('name', 'unknown')} (ID: {ch.get('id', 'unknown')})")
                else:
                    print("   - Botが参加しているチャンネルがありません")
            else:
                print("❌ チャンネル一覧取得失敗")
        except SlackApiError as e:
            print(f"❌ チャンネル一覧取得エラー: {e.response.get('error', 'Unknown error')}")
        
        # 4. 権限確認
        print("\n4. 権限確認")
        user_id = auth_response.get('user_id')
        if user_id:
            try:
                # メッセージ送信テスト（DMで）
                test_response = client.chat_postMessage(
                    channel=user_id,
                    text="🔧 API確認テストメッセージです。このメッセージが表示されれば権限は正常です。"
                )
                print("✅ メッセージ送信権限: 正常")
            except SlackApiError as e:
                print(f"❌ メッセージ送信権限エラー: {e.response.get('error', 'Unknown error')}")
        else:
            print("⚠️  ユーザーIDが取得できませんでした")
        
        # 5. 履歴取得テスト
        print("\n5. 履歴取得テスト")
        try:
            if bot_channels:
                test_channel = bot_channels[0].get('id')
                if test_channel:
                    history_response = client.conversations_history(channel=test_channel, limit=1)
                    print(f"✅ 履歴取得権限: 正常 (チャンネル: #{bot_channels[0].get('name', 'unknown')})")
                else:
                    print("⚠️  テストチャンネルIDが取得できませんでした")
            else:
                print("⚠️  履歴取得テスト: Botが参加しているチャンネルがありません")
        except SlackApiError as e:
            print(f"❌ 履歴取得権限エラー: {e.response.get('error', 'Unknown error')}")
        
        print("\n🎉 Slack API確認完了！")
        return True
        
    except SlackApiError as e:
        print(f"❌ Slack API エラー: {e.response.get('error', 'Unknown error')}")
        if e.response.get('error') == 'invalid_auth':
            print("   → Bot Tokenが無効です。トークンを確認してください。")
        elif e.response.get('error') == 'missing_scope':
            print("   → 必要な権限が不足しています。スコープを確認してください。")
        return False
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        return False

def check_environment():
    """環境変数の確認"""
    print("🔍 環境変数確認")
    
    required_vars = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN"),
    }
    
    all_set = True
    for var_name, var_value in required_vars.items():
        if var_value:
            print(f"✅ {var_name}: 設定済み")
        else:
            print(f"❌ {var_name}: 未設定")
            all_set = False
    
    return all_set

if __name__ == "__main__":
    print("=" * 50)
    print("Slack API 状況確認ツール")
    print("=" * 50)
    
    # 環境変数確認
    env_ok = check_environment()
    print()
    
    if env_ok:
        # Slack API確認
        api_ok = check_slack_api()
        
        print("\n" + "=" * 50)
        if api_ok:
            print("🎉 すべて正常です！SlackBotが使用可能です。")
        else:
            print("⚠️  Slack APIに問題があります。設定を確認してください。")
    else:
        print("❌ 環境変数が不足しています。.envファイルを確認してください。") 