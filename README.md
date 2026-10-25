# Todoアプリ

Flask と Google スプレッドシートで作った Todo 管理の Web アプリです。
AIエンジニア講座の課題として作成しました。

**公開URL:** https://todo-app-p1sg.onrender.com/

> 無料プランのため、しばらくアクセスがないとスリープします。最初の表示に 30 秒〜1 分ほどかかることがあります。

## できること

- **一覧表示:** 登録した Todo をカード形式で表示
- **追加:** タイトル（必須）・内容・期限を入力して登録
- **編集:** 登録済みの Todo の内容を書き換え
- **削除:** 確認ダイアログを出してから削除
- **完了チェック:** 「完了」ボタンで完了にすると、グレー表示・取り消し線になる（「未完了に戻す」で元に戻せる）

データはすべて Google スプレッドシートに保存されます。

## 使用技術

| 分類 | 使ったもの |
|---|---|
| 言語 | Python 3.12 |
| Web フレームワーク | Flask |
| データの保存 | Google スプレッドシート（gspread で読み書き） |
| 公開先 | Render（gunicorn で起動） |
| その他 | python-dotenv（環境変数の読み込み） |

## ファイル構成

```
├── app.py              # アプリ本体（一覧・追加・編集・削除）
├── templates/
│   ├── index.html      # 一覧と追加フォーム
│   └── edit.html       # 編集フォーム
├── static/
│   └── style.css       # デザイン
├── test_sheets.py      # スプレッドシートの接続テスト
├── requirements.txt    # 必要なパッケージ
└── .python-version     # Render で使う Python のバージョン
```

## スプレッドシートの形式

`todos` という名前のシートを使います。1 行目は次の見出しです。

| id | title | content | due_date | created_at | updated_at | done |
|---|---|---|---|---|---|---|

- `id` は追加するたびに自動で番号が振られます。
- `created_at` と `updated_at` には日本時間の日時が入ります。
- `done` は完了したら「済」、未完了なら空になります。

## 手元で動かす方法

1. リポジトリをダウンロードして、仮想環境を作ります。

   ```
   git clone https://github.com/risa-harapeko/todo-app.git
   cd todo-app
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Google Cloud でサービスアカウントを作り、鍵ファイルを `credentials.json` という名前でフォルダに置きます。

3. スプレッドシートを、サービスアカウントのメールアドレスに「編集者」として共有します。

4. `.env` ファイルを作り、スプレッドシートの ID を書きます。

   ```
   SPREADSHEET_ID=スプレッドシートのID
   ```

5. 接続を確かめてから、アプリを起動します。

   ```
   python test_sheets.py
   python app.py
   ```

   ブラウザで http://127.0.0.1:5000 を開きます。

`credentials.json` と `.env` は秘密の情報なので、`.gitignore` で GitHub に上げないようにしています。

## Render での公開設定

| 項目 | 値 |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| 環境変数 `SPREADSHEET_ID` | スプレッドシートの ID |
| 環境変数 `GOOGLE_CREDENTIALS` | `credentials.json` の中身をまるごと |

Render 上では、`credentials.json` の代わりに環境変数 `GOOGLE_CREDENTIALS` から認証情報を読み込みます。
