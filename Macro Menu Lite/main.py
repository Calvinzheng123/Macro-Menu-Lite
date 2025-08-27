from flask import Flask, jsonify, render_template
import json, os

app = Flask(__name__, template_folder="templates", static_folder="static")

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "items_for_web.json")

def load_items():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/data/items")
def items():
    return jsonify(load_items())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
