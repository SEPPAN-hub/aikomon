import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

def get_channels():
    """チャンネル一覧を取得"""
    if not SLACK_BOT_TOKEN:
        print("❌ SLACK_BOT_TOKENが設定されていません")
        return
    
    client = WebClient(token=SLACK_BOT_TOKEN)
    
    try:
        print("🔍 チャンネル一覧取得中...")
        channels_response = client.conversations_list(types="public_channel,private_channel")
        
        if channels_response and channels_response.get('ok'):
            channels = channels_response.get('channels', [])
            print(f"✅ 総チャンネル数: {len(channels)}")
            
            print("\n📋 最初の5つのチャンネル:")
            for i, ch in enumerate(channels[:5], 1):
                name = ch.get('name', 'unknown')
                ch_id = ch.get('id', 'unknown')
                is_private = ch.get('is_private', False)
                is_member = ch.get('is_member', False)
                
                privacy = "🔒 プライベート" if is_private else "🌐 パブリック"
                member_status = "✅ Bot参加中" if is_member else "❌ Bot未参加"
                
                print(f"{i}. #{name}")
                print(f"   ID: {ch_id}")
                print(f"   種類: {privacy}")
                print(f"   参加状況: {member_status}")
                print()
        else:
            print("❌ チャンネル一覧取得失敗")
            
    except SlackApiError as e:
        print(f"❌ Slack API エラー: {e.response.get('error', 'Unknown error')}")
        if e.response.get('error') == 'missing_scope':
            print("   → channels:read スコープが必要です")
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")

if __name__ == "__main__":
    get_channels() 