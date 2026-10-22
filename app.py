from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "Todoアプリ 準備中"

if __name__ == "__main__":
    app.run(debug=True)