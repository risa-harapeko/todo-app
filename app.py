import json
import os
from datetime import datetime, timedelta, timezone

import gspread
from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, url_for

load_dotenv()

app = Flask(__name__)

# Renderのサーバーは世界標準時なので、日本時間を明示する
JST = timezone(timedelta(hours=9))


def get_worksheet():
    # 公開先(Render)では環境変数 GOOGLE_CREDENTIALS から、手元では credentials.json から読む
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        gc = gspread.service_account_from_dict(json.loads(creds_json))
    else:
        gc = gspread.service_account(filename="credentials.json")
    return gc.open_by_key(os.environ["SPREADSHEET_ID"]).worksheet("todos")


@app.route("/")
def index():
    todos = get_worksheet().get_all_records()
    return render_template("index.html", todos=todos)


@app.route("/add", methods=["POST"])
def add():
    ws = get_worksheet()
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    due_date = request.form.get("due_date", "")

    if not title:
        todos = ws.get_all_records()
        return render_template(
            "index.html",
            todos=todos,
            error="タイトルを入力してください。",
            form=request.form,
        ), 400

    # 今あるidの最大値+1を新しいidにする
    ids = [int(t["id"]) for t in ws.get_all_records() if str(t["id"]).isdigit()]
    new_id = max(ids, default=0) + 1
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

    ws.append_row([new_id, title, content, due_date, now, now])
    return redirect(url_for("index"))


@app.route("/edit/<int:todo_id>", methods=["GET", "POST"])
def edit(todo_id):
    ws = get_worksheet()
    todos = ws.get_all_records()

    # 1行目は見出しなので、データのi番目はシートの i+2 行目
    for i, t in enumerate(todos):
        if str(t["id"]) == str(todo_id):
            todo, row = t, i + 2
            break
    else:
        abort(404)

    if request.method == "GET":
        return render_template("edit.html", todo=todo)

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    due_date = request.form.get("due_date", "")

    if not title:
        form_todo = {**todo, "title": title, "content": content, "due_date": due_date}
        return render_template(
            "edit.html", todo=form_todo, error="タイトルを入力してください。"
        ), 400

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    # B〜D列(title, content, due_date)とF列(updated_at)を書き換え、E列(created_at)はそのまま
    ws.update(range_name=f"B{row}:F{row}", values=[[title, content, due_date, todo["created_at"], now]])
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
