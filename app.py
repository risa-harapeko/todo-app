import json
import os

import gspread
from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv()

app = Flask(__name__)


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


if __name__ == "__main__":
    app.run(debug=True)
