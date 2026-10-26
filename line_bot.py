"""LINEに送ったメッセージを、Todoとして登録する受付窓口

送り方の例：
  資料送る          → 期日は今日
  明日 資料送る     → 期日は明日
  あさって 資料送る → 期日は明後日
  10/30 資料送る    → 期日は10月30日
  完了              → 未完了のやることをボタンで出し、タップで完了にする
"""
import os
import re
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Blueprint, abort, request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PostbackAction,
    QuickReply,
    QuickReplyItem,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, PostbackEvent, TextMessageContent

import sheets

load_dotenv()

JST = timezone(timedelta(hours=9))

line_bp = Blueprint("line", __name__)
handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET", "not-set"))
configuration = Configuration(access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""))


def parse_message(text):
    """メッセージを（タイトル, 期日 YYYY-MM-DD）に分ける"""
    today = datetime.now(JST).date()
    text = text.replace("　", " ").strip()
    due = today
    title = text

    parts = text.split(" ", 1)
    if len(parts) == 2:
        head, rest = parts[0], parts[1].strip()
        if head in ("今日", "きょう"):
            due, title = today, rest
        elif head in ("明日", "あした"):
            due, title = today + timedelta(days=1), rest
        elif head in ("明後日", "あさって"):
            due, title = today + timedelta(days=2), rest
        else:
            m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", head)
            if m:
                try:
                    d = date(today.year, int(m.group(1)), int(m.group(2)))
                    if d < today:
                        d = date(today.year + 1, d.month, d.day)
                    due, title = d, rest
                except ValueError:
                    pass

    return title[:50], due.isoformat()


def reply(reply_token, text, quick_reply=None):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text, quick_reply=quick_reply)],
            )
        )


def check_user(event):
    """自分からのメッセージなら True。それ以外は返信して False"""
    user_id = event.source.user_id
    allowed_id = os.environ.get("LINE_ALLOWED_USER_ID")

    # 準備中：登録はせず、自分のIDを返す（このIDをRenderに登録すると使えるようになる）
    if not allowed_id:
        reply(event.reply_token, f"準備中です。あなたのユーザーIDは\n{user_id}\nです。")
        return False

    # 自分以外からのメッセージは処理しない
    if user_id != allowed_id:
        reply(event.reply_token, "このアカウントからは登録できません。")
        return False

    return True


def send_done_choices(reply_token):
    """未完了のやることを、期日の近い順に最大13件ボタンで出す"""
    todos = sheets.get_worksheet().get_all_records()
    undone = [t for t in todos if not sheets.is_done(t)]
    if not undone:
        reply(reply_token, "未完了のやることはありません")
        return

    # 期日のないものは最後に回す
    undone.sort(key=lambda t: sheets.parse_date(t.get("due_date", "")) or date.max)

    items = []
    for t in undone[:13]:  # クイックリプライのボタンは13個まで
        title = str(t["title"])
        items.append(
            QuickReplyItem(
                action=PostbackAction(
                    label=title[:20],  # ボタンの文字は20文字まで
                    data=f"done:{t['id']}",
                    display_text=f"✓ {title}",
                )
            )
        )
    reply(reply_token, "どれが終わりましたか？", quick_reply=QuickReply(items=items))


@line_bp.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    if not check_user(event):
        return

    # 「完了」とだけ送られたら、登録ではなく完了にするやることを選んでもらう
    if event.message.text.replace("　", " ").strip() == "完了":
        send_done_choices(event.reply_token)
        return

    title, due_date = parse_message(event.message.text)
    if not title:
        reply(event.reply_token, "やることを入力してください。")
        return

    try:
        sheets.add_todo(title, "", due_date)
    except Exception:
        reply(event.reply_token, "登録できませんでした。時間をおいてもう一度送ってください。")
        raise

    reply(event.reply_token, f"登録しました\n{title}\n期日：{due_date}")


@handler.add(PostbackEvent)
def handle_postback(event):
    if not check_user(event):
        return

    data = event.postback.data
    if not data.startswith("done:"):
        return

    ws = sheets.get_worksheet()
    todos = ws.get_all_records()
    found = sheets.find_todo(ws, data.removeprefix("done:"), todos=todos)
    if found is None:
        reply(event.reply_token, "そのやることは見つかりませんでした（削除された可能性があります）")
        return

    todo, row = found
    if sheets.is_done(todo):
        reply(event.reply_token, "すでに完了しています")
        return

    sheets.set_done(ws, row, True)
    # 今完了にした1件は、読み込んだ todos にはまだ入っていないので +1 する
    count = sheets.count_completed_today(todos) + 1
    reply(event.reply_token, f"完了しました！ {todo['title']}　今日の完了：{count}件")
