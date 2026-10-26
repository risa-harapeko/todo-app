"""スプレッドシート(todosシート)とのやりとりをまとめたもの

Web画面(app.py)とLINE(line_bot.py)の両方から使う
"""
import json
import os
from datetime import date, datetime, timedelta, timezone

import gspread
from dotenv import load_dotenv

load_dotenv()

# Renderのサーバーは世界標準時なので、日本時間を明示する
JST = timezone(timedelta(hours=9))


def now_str():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def today():
    return datetime.now(JST).date()


def parse_date(value):
    """シートの日付（2026-10-30 や 2026/10/30）を date にする。空や読めないときは None"""
    text = str(value).strip().replace("/", "-")
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def is_done(todo):
    return todo.get("done") == "済"


INTERRUPT = "割り込み"
TODAY_LIMIT = 3  # 「今日の3つ」に入れられる数


def is_doing(todo):
    """「今やっていること」なら True（K列 doing が TRUE）"""
    return str(todo.get("doing", "")).strip().upper() == "TRUE"


def is_today(todo):
    """「今日の3つ」に入っていれば True（I列 today_date が日本時間の今日）"""
    return not is_done(todo) and str(todo.get("today_date", "")).strip() == today().isoformat()


def is_interrupt(todo):
    return todo.get("type") == INTERRUPT


def get_worksheet():
    # 公開先(Render)では環境変数 GOOGLE_CREDENTIALS から、手元では credentials.json から読む
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        gc = gspread.service_account_from_dict(json.loads(creds_json))
    else:
        gc = gspread.service_account(filename="credentials.json")
    return gc.open_by_key(os.environ["SPREADSHEET_ID"]).worksheet("todos")


def add_todo(title, content, due_date, ws=None, todo_type=""):
    """Todoを1行追加する

    列: id, title, content, due_date, created_at, updated_at, done, completed_at,
        today_date, type, doing
    """
    if ws is None:
        ws = get_worksheet()

    # 今あるidの最大値+1を新しいidにする
    ids = [int(t["id"]) for t in ws.get_all_records() if str(t["id"]).isdigit()]
    new_id = max(ids, default=0) + 1
    now = now_str()

    ws.append_row([new_id, title, content, due_date, now, now, "", "", "", todo_type, ""])
    return new_id


def find_todo(ws, todo_id, todos=None):
    """idでTodoを探して（Todo, シートの行番号）を返す。見つからなければ None"""
    if todos is None:
        todos = ws.get_all_records()
    # 1行目は見出しなので、データのi番目はシートの i+2 行目
    for i, t in enumerate(todos):
        if str(t["id"]) == str(todo_id):
            return t, i + 2
    return None


def set_done(ws, row, done):
    """完了／未完了を切り替える。F列(updated_at)・G列(done)・H列(completed_at)を書き換える

    完了にしたときは、I列(today_date)とK列(doing)も空にする（今日の3つ・今やっていることから外す）
    """
    now = now_str()
    if done:
        ws.batch_update([
            {"range": f"F{row}:H{row}", "values": [[now, "済", now]]},
            {"range": f"I{row}", "values": [[""]]},
            {"range": f"K{row}", "values": [[""]]},
        ])
    else:
        ws.update(range_name=f"F{row}:H{row}", values=[[now, "", ""]])


def count_today(todos):
    return sum(1 for t in todos if is_today(t))


def set_today(ws, row, on):
    """「今日の3つ」に入れる／外す（I列 today_date）"""
    ws.update(range_name=f"I{row}", values=[[today().isoformat() if on else ""]])


def set_type(ws, row, todo_type):
    """J列 type を書き換える（「割り込み」または空）"""
    ws.update(range_name=f"J{row}", values=[[todo_type]])


def start_doing(ws, row, todos):
    """指定した行を「今やっていること」にし、ほかの doing は空にする（K列）"""
    data = [
        {"range": f"K{i + 2}", "values": [[""]]}
        for i, t in enumerate(todos)
        if is_doing(t) and i + 2 != row
    ]
    data.append({"range": f"K{row}", "values": [["TRUE"]]})
    ws.batch_update(data)


def stop_doing(ws, row):
    """「今やっていること」を中断する（K列 doing を空にする）"""
    ws.update(range_name=f"K{row}", values=[[""]])


def overdue_todos(todos):
    """未完了で、期日が今日より前のTodoを（Todo, 行番号）のリストで返す"""
    result = []
    for i, t in enumerate(todos):
        due = parse_date(t.get("due_date", ""))
        if not is_done(t) and due and due < today():
            result.append((t, i + 2))
    return result


def postpone_to_tomorrow(ws, rows):
    """指定した行の期日を明日にする。D列(due_date)とF列(updated_at)を書き換える"""
    if not rows:
        return
    tomorrow = (today() + timedelta(days=1)).isoformat()
    now = now_str()
    data = []
    for row in rows:
        data.append({"range": f"D{row}", "values": [[tomorrow]]})
        data.append({"range": f"F{row}", "values": [[now]]})
    ws.batch_update(data)


def count_completed_today(todos):
    """今日（日本時間）完了にしたTodoの数"""
    today_str = today().isoformat()
    return sum(
        1 for t in todos if is_done(t) and str(t.get("completed_at", "")).startswith(today_str)
    )
