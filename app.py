import os
import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

MASTER_PATH = "master.md"
FRIEREN_PATH = "frieren_note.md"

def read_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
@app.route("/sync", methods=["GET"])
def sync_state():
    master_content = read_file(MASTER_PATH)
    frieren_content = read_file(FRIEREN_PATH)
    return jsonify({
        "status": "success",
        "master": master_content,
        "frieren_note": frieren_content,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/update", methods=["POST"])
def update_state():
    data = request.json or {}
    new_note = data.get("note", "")
    if new_note:
        write_file(FRIEREN_PATH, new_note)
        return jsonify({"status": "updated", "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    return jsonify({"status": "error", "message": "No note provided"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
