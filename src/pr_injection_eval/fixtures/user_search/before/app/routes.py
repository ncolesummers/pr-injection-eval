from flask import Flask, abort, jsonify

from app import db

app = Flask(__name__)


@app.get("/items/<int:item_id>")
def get_item(item_id: int):
    item = db.get_item(item_id)
    if item is None:
        abort(404)
    return jsonify(dict(item))
