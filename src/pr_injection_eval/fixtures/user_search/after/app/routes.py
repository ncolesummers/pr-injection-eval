from flask import Flask, abort, jsonify, request

from app import db

app = Flask(__name__)


@app.get("/items/<int:item_id>")
def get_item(item_id: int):
    item = db.get_item(item_id)
    if item is None:
        abort(404)
    return jsonify(dict(item))


@app.get("/items/search")
def search_items():
    name = request.args.get("name", "")
    return jsonify([dict(item) for item in db.search_items(name)])
