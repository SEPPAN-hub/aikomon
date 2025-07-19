import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

def check_bot_info():
    """現在のBot情報を詳細に確認"""
    if not SLACK_BOT_TOKEN:
        print("❌ SLACK_BOT_TOKENが設定されていません")
        return
    
    client = WebClient(token=SLACK_BOT_TOKEN)
    
    try:
        print("🔍 現在のBot情報確認中...")
        print(f"Bot Token: {SLACK_BOT_TOKEN[:15]}...")
        print()
        
        # 認証テスト
        auth_response = client.auth_test()
        
        print("📋 Bot詳細情報:")
        print(f"   Bot名: {auth_response.get('user', 'N/A')}")
        print(f"   Bot ID: {auth_response.get('bot_id', 'N/A')}")
        print(f"   ユーザーID: {auth_response.get('user_id', 'N/A')}")
        print(f"   ワークスペース名: {auth_response.get('team', 'N/A')}")
        print(f"   ワークスペースID: {auth_response.get('team_id', 'N/A')}")
        print(f"   URL: {auth_response.get('url', 'N/A')}")
        
        # Bot情報をさらに詳しく取得
        bot_id = auth_response.get('bot_id')
        if bot_id:
            try:
                print("\n🤖 Bot詳細設定:")
                bot_info = client.bots_info(bot=bot_id)
                if bot_info and bot_info.get('ok'):
                    bot_data = bot_info.get('bot', {})
                    print(f"   Bot名: {bot_data.get('name', 'N/A')}")
                    print(f"   Bot ID: {bot_data.get('id', 'N/A')}")
                    print(f"   削除済み: {bot_data.get('deleted', 'N/A')}")
                    print(f"   アイコン: {bot_data.get('icons', {}).get('image_48', 'N/A')}")
                else:
                    print("   ⚠️  Bot詳細情報取得失敗")
            except SlackApiError as e:
                print(f"   ⚠️  Bot詳細情報取得エラー: {e.response.get('error', 'Unknown error')}")
        
        print("\n" + "="*50)
        print("このBotが正しいかどうか確認してください:")
        print(f"• Bot名: {auth_response.get('user', 'N/A')}")
        print(f"• ワークスペース: {auth_response.get('team', 'N/A')}")
        print("="*50)
        
    except SlackApiError as e:
        print(f"❌ Slack API エラー: {e.response.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")

if __name__ == "__main__":
    check_bot_info() 