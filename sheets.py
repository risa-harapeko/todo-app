"""スプレッドシート(todosシート)とのやりとりをまとめたもの

Web画面(app.py)とLINE(line_bot.py)の両方から使う
"""
import json
import os
from datetime import datetime, timedelta, timezone

import gspread
from dotenv import load_dotenv

load_dotenv()

# Renderのサーバーは世界標準時なので、日本時間を明示する
JST = timezone(timedelta(hours=9))


def now_str():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def get_worksheet():
    # 公開先(Render)では環境変数 GOOGLE_CREDENTIALS から、手元では credentials.json から読む
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        gc = gspread.service_account_from_dict(json.loads(creds_json))
    else:
        gc = gspread.service_account(filename="credentials.json")
    return gc.open_by_key(os.environ["SPREADSHEET_ID"]).worksheet("todos")


def add_todo(title, content, due_date, ws=None):
    """Todoを1行追加する（列: id, title, content, due_date, created_at, updated_at, done）"""
    if ws is None:
        ws = get_worksheet()

    # 今あるidの最大値+1を新しいidにする
    ids = [int(t["id"]) for t in ws.get_all_records() if str(t["id"]).isdigit()]
    new_id = max(ids, default=0) + 1
    now = now_str()

    ws.append_row([new_id, title, content, due_date, now, now, ""])
    return new_id
