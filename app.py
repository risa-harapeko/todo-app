from flask import Flask, abort, redirect, render_template, request, url_for

import sheets
from line_bot import line_bp

app = Flask(__name__)
app.register_blueprint(line_bp)


NOTICES = {
    "today_full": "今日の3つはいっぱいです。どれかを外してから入れてください",
}


def render_index(todos, status=200, **extra):
    """一覧ページを、上から「今やっていること → 今日の3つ → 割り込み箱 → 期日切れ → その他」に分けて表示する"""
    undone = [t for t in todos if not sheets.is_done(t)]
    doing = next((t for t in undone if sheets.is_doing(t)), None)
    today3 = [t for t in undone if sheets.is_today(t)]
    interrupts = [
        t for t in undone
        if sheets.is_interrupt(t) and not sheets.is_today(t) and t is not doing
    ]
    overdue = [t for t, _ in sheets.overdue_todos(todos)]

    # 上の枠に出ているものは「その他」に重ねて出さない
    shown = {id(t) for t in [doing, *today3, *interrupts, *overdue] if t is not None}
    others = [t for t in undone if id(t) not in shown]
    done_todos = [t for t in todos if sheets.is_done(t)]

    return render_template(
        "index.html",
        todos=todos,
        doing=doing,
        today3=today3,
        today_limit=sheets.TODAY_LIMIT,
        interrupts=interrupts,
        overdue=overdue,
        others=others,
        done_todos=done_todos,
        notice=NOTICES.get(request.args.get("notice", "")),
        **extra,
    ), status


@app.route("/")
def index():
    return render_index(sheets.get_worksheet().get_all_records())


@app.route("/add", methods=["POST"])
def add():
    ws = sheets.get_worksheet()
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    due_date = request.form.get("due_date", "")
    todo_type = sheets.INTERRUPT if request.form.get("interrupt") else ""

    if not title:
        return render_index(
            ws.get_all_records(),
            status=400,
            error="タイトルを入力してください。",
            form=request.form,
        )

    sheets.add_todo(title, content, due_date, ws=ws, todo_type=todo_type)
    return redirect(url_for("index"))


def find_todo(ws, todo_id):
    found = sheets.find_todo(ws, todo_id)
    if found is None:
        abort(404)
    return found


def find_todo_in(todos, todo_id):
    """読み込み済みの todos から探す（シートを読み直さずに済む）"""
    found = sheets.find_todo(None, todo_id, todos=todos)
    if found is None:
        abort(404)
    return found


@app.route("/edit/<int:todo_id>", methods=["GET", "POST"])
def edit(todo_id):
    ws = sheets.get_worksheet()
    todo, row = find_todo(ws, todo_id)

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

    now = sheets.now_str()
    # B〜D列(title, content, due_date)とF列(updated_at)を書き換え、E列(created_at)はそのまま
    ws.update(range_name=f"B{row}:F{row}", values=[[title, content, due_date, todo["created_at"], now]])
    return redirect(url_for("index"))


@app.route("/toggle/<int:todo_id>", methods=["POST"])
def toggle(todo_id):
    ws = sheets.get_worksheet()
    todo, row = find_todo(ws, todo_id)
    # 完了なら未完了に、未完了なら完了に切り替える
    sheets.set_done(ws, row, not sheets.is_done(todo))
    return redirect(url_for("index"))


@app.route("/complete/<int:todo_id>", methods=["POST"])
def complete(todo_id):
    # 期日切れの枠の「終わった」。二度押しで未完了に戻らないよう、完了にするだけ
    ws = sheets.get_worksheet()
    todo, row = find_todo(ws, todo_id)
    if not sheets.is_done(todo):
        sheets.set_done(ws, row, True)
    return redirect(url_for("index"))


@app.route("/postpone/<int:todo_id>", methods=["POST"])
def postpone(todo_id):
    ws = sheets.get_worksheet()
    _, row = find_todo(ws, todo_id)
    sheets.postpone_to_tomorrow(ws, [row])
    return redirect(url_for("index"))


@app.route("/postpone_all", methods=["POST"])
def postpone_all():
    # 押した時点のシートで期日切れを数え直してから、まとめて延期する
    ws = sheets.get_worksheet()
    rows = [row for _, row in sheets.overdue_todos(ws.get_all_records())]
    sheets.postpone_to_tomorrow(ws, rows)
    return redirect(url_for("index"))


@app.route("/star/<int:todo_id>", methods=["POST"])
def star(todo_id):
    # 「今日の3つ」に入れる。3件そろっていたら入れずにお知らせを出す
    ws = sheets.get_worksheet()
    todos = ws.get_all_records()
    todo, row = find_todo_in(todos, todo_id)
    if sheets.is_done(todo) or sheets.is_today(todo):
        return redirect(url_for("index"))
    if sheets.count_today(todos) >= sheets.TODAY_LIMIT:
        return redirect(url_for("index", notice="today_full"))
    sheets.set_today(ws, row, True)
    return redirect(url_for("index"))


@app.route("/unstar/<int:todo_id>", methods=["POST"])
def unstar(todo_id):
    ws = sheets.get_worksheet()
    _, row = find_todo(ws, todo_id)
    sheets.set_today(ws, row, False)
    return redirect(url_for("index"))


@app.route("/start/<int:todo_id>", methods=["POST"])
def start(todo_id):
    # 「今やっていること」にする。ほかに始めていたものは中断になる（確認はブラウザ側で出す）
    ws = sheets.get_worksheet()
    todos = ws.get_all_records()
    todo, row = find_todo_in(todos, todo_id)
    if not sheets.is_done(todo):
        sheets.start_doing(ws, row, todos)
    return redirect(url_for("index"))


@app.route("/stop/<int:todo_id>", methods=["POST"])
def stop(todo_id):
    # 「中断する」。今やっていることから外すだけで、完了にはしない
    ws = sheets.get_worksheet()
    _, row = find_todo(ws, todo_id)
    sheets.stop_doing(ws, row)
    return redirect(url_for("index"))


@app.route("/make_normal/<int:todo_id>", methods=["POST"])
def make_normal(todo_id):
    # 割り込み箱から「通常に移す」
    ws = sheets.get_worksheet()
    _, row = find_todo(ws, todo_id)
    sheets.set_type(ws, row, "")
    return redirect(url_for("index"))


@app.route("/delete/<int:todo_id>", methods=["POST"])
def delete(todo_id):
    ws = sheets.get_worksheet()
    _, row = find_todo(ws, todo_id)
    ws.delete_rows(row)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
