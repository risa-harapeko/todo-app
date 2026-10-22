import json
import os

import gspread
from dotenv import load_dotenv

load_dotenv()

# 公開先(Render)では環境変数から、手元では credentials.json から読む
gc = gspread.service_account(filename="credentials.json")

ws = gc.open_by_key(os.environ["SPREADSHEET_ID"]).worksheet("todos")
print("接続成功！ 見出し:", ws.row_values(1))
print("データ件数:", len(ws.get_all_records()))