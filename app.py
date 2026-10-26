from flask import Flask, abort, redirect, render_template, request, url_for

import sheets
from line_bot import line_bp

app = Flask(__name__)
app.register_blueprint(line_bp)


@app.route("/")
def index():
    todos = sheets.get_worksheet().get_all_records()
    overdue = [t for t, _ in sheets.overdue_todos(todos)]
    return render_template("index.html", todos=todos, overdue=overdue)


@app.route("/add", methods=["POST"])
def add():
    ws = sheets.get_worksheet()
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    due_date = request.form.get("due_date", "")

    if not title:
        todos = ws.get_all_records()
        return render_template(
            "index.html",
            todos=todos,
            overdue=[t for t, _ in sheets.overdue_todos(todos)],
            error="タイトルを入力してください。",
            form=request.form,
        ), 400

    sheets.add_todo(title, content, due_date, ws=ws)
    return redirect(url_for("index"))


def find_todo(ws, todo_id):
    found = sheets.find_todo(ws, todo_id)
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


@app.route("/delete/<int:todo_id>", methods=["POST"])
def delete(todo_id):
    ws = sheets.get_worksheet()
    _, row = find_todo(ws, todo_id)
    ws.delete_rows(row)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
