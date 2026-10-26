"""LINEに送ったメッセージを、Todoとして登録する受付窓口

送り方の例：
  資料送る          → 期日は今日
  明日 資料送る     → 期日は明日
  あさって 資料送る → 期日は明後日
  10/30 資料送る    → 期日は10月30日
  完了              → 未完了のやることをボタンで出し、タップで完了にする
"""
import logging
import os
import re
from collections import deque
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
logger = logging.getLogger(__name__)

# 処理済みのメッセージのID（LINEが同じメッセージを再送してきても、二重に登録しないため）
_handled_ids = set()
_handled_order = deque()


def mark_handled(event):
    """初めてのメッセージなら覚えて True、処理済み（再送）なら False"""
    event_id = getattr(event, "webhook_event_id", None)
    if not event_id:
        return True
    if event_id in _handled_ids:
        return False
    _handled_ids.add(event_id)
    _handled_order.append(event_id)
    if len(_handled_order) > 1000:  # 古いものから忘れる
        _handled_ids.discard(_handled_order.popleft())
    return True


def forget_handled(event):
    """登録に失敗したときは忘れて、LINEの再送でもう一度試せるようにする"""
    _handled_ids.discard(getattr(event, "webhook_event_id", None))


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
    # 返信に失敗しても（返信用の鍵の期限切れなど）エラーにしない。
    # エラーにするとLINEが同じメッセージを再送してきて、登録がくり返されるため
    try:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=text, quick_reply=quick_reply)],
                )
            )
    except Exception:
        logger.exception("LINEへの返信に失敗しました")


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
    if not mark_handled(event):
        return
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
        forget_handled(event)
        reply(event.reply_token, "登録できませんでした。時間をおいてもう一度送ってください。")
        raise

    reply(event.reply_token, f"登録しました\n{title}\n期日：{due_date}")


@handler.add(PostbackEvent)
def handle_postback(event):
    if not mark_handled(event):
        return
    if not check_user(event):
        return

    data = event.postback.data
    if not data.startswith("done:"):
        return

    try:
        ws = sheets.get_worksheet()
        todos = ws.get_all_records()
    except Exception:
        forget_handled(event)
        raise
    found = sheets.find_todo(ws, data.removeprefix("done:"), todos=todos)
    if found is None:
        reply(event.reply_token, "そのやることは見つかりませんでした（削除された可能性があります）")
        return

    todo, row = found
    if sheets.is_done(todo):
        reply(event.reply_token, "すでに完了しています")
        return

    try:
        sheets.set_done(ws, row, True)
    except Exception:
        forget_handled(event)
        raise
    # 今完了にした1件は、読み込んだ todos にはまだ入っていないので +1 する
    count = sheets.count_completed_today(todos) + 1
    reply(event.reply_token, f"完了しました！ {todo['title']}　今日の完了：{count}件")
