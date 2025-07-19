# SlackBot 401エラー解決ガイド

## 1. Slack Appの基本設定

### 1.1 App Manifest設定
```json
{
  "display_information": {
    "name": "Slack AI Komon",
    "description": "Slackメッセージをベクトル化してAI検索できるBot",
    "background_color": "#000000"
  },
  "features": {
    "bot_user": {
      "display_name": "Slack AI Komon",
      "always_online": true
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "chat:write",
        "channels:history",
        "channels:read",
        "groups:history",
        "groups:read",
        "im:history",
        "im:read",
        "mpim:history",
        "mpim:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "request_url": "https://your-app.onrender.com/slack/events",
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im",
        "message.mpim"
      ]
    },
    "socket_mode_enabled": false
  }
}
```

### 1.2 必要なBot Token Scopes
- `app_mentions:read` - @メンションを読み取り
- `chat:write` - メッセージを送信
- `channels:history` - チャンネル履歴を読み取り
- `channels:read` - チャンネル情報を読み取り

### 1.3 必要なUser Token Scopes
- `channels:history` - チャンネル履歴を読み取り
- `channels:read` - チャンネル情報を読み取り

## 2. 環境変数設定

### 2.1 必要な環境変数
```bash
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
OPENAI_API_KEY=your_openai_api_key
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
```

### 2.2 Bot Tokenの取得方法
1. Slack App設定画面 → OAuth & Permissions
2. "Bot User OAuth Token" をコピー
3. `xoxb-` で始まるトークン

### 2.3 App Tokenの取得方法
1. Slack App設定画面 → Basic Information
2. "App-Level Tokens" セクション
3. "Generate Token and Scopes" をクリック
4. `xapp-` で始まるトークン

## 3. 401エラーの解決手順

### 3.1 トークンの確認
```bash
# Bot Tokenの形式確認
echo $SLACK_BOT_TOKEN
# 期待値: xoxb-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# App Tokenの形式確認  
echo $SLACK_APP_TOKEN
# 期待値: xapp-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3.2 Botのチャンネル参加
1. SlackワークスペースでBotを招待
2. `/invite @Slack AI Komon` を実行
3. Botがチャンネルに参加していることを確認

### 3.3 Appの再インストール
1. Slack App設定画面 → Install App
2. "Reinstall to Workspace" をクリック
3. 必要な権限を承認

### 3.4 Event Subscriptions設定
1. Request URL: `https://your-app.onrender.com/slack/events`
2. Bot Events:
   - `app_mention`
   - `message.channels`
   - `message.groups`
   - `message.im`
   - `message.mpim`

## 4. ローカルテスト方法

### 4.1 ngrokでの外部公開
```bash
# ngrokインストール
npm install -g ngrok

# ローカルサーバー起動
python slack_vector_bot.py

# 別ターミナルでngrok起動
ngrok http 3000

# 表示されたURLをSlack AppのRequest URLに設定
# 例: https://abc123.ngrok.io/slack/events
```

### 4.2 テスト実行
```bash
# 環境変数設定確認
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('SUPABASE_URL:', bool(os.getenv('SUPABASE_URL'))); print('SLACK_BOT_TOKEN:', bool(os.getenv('SLACK_BOT_TOKEN')))"

# Bot起動テスト
python slack_vector_bot.py
```

## 5. よくある問題と解決方法

### 5.1 "invalid_auth" エラー
- Bot Tokenが正しくない
- Appがワークスペースにインストールされていない
- トークンの権限が不足している

### 5.2 "missing_scope" エラー
- 必要なスコープが設定されていない
- Appを再インストールして権限を更新

### 5.3 "channel_not_found" エラー
- Botがチャンネルに参加していない
- チャンネル名が間違っている

## 6. デバッグ方法

### 6.1 ログ確認
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 6.2 Slack APIテスト
```python
from slack_sdk import WebClient
client = WebClient(token=SLACK_BOT_TOKEN)
response = client.auth_test()
print(response)
```

### 6.3 環境変数確認
```python
import os
from dotenv import load_dotenv
load_dotenv()
print("SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("SLACK_BOT_TOKEN:", os.getenv("SLACK_BOT_TOKEN")[:10] + "...")
``` 