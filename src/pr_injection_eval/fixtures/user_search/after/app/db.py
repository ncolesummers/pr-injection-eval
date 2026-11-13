import sqlite3

DB_PATH = "inventory.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_item(item_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        cur = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        return cur.fetchone()


def search_items(name: str) -> list[sqlite3.Row]:
    with connect() as conn:
        query = f"SELECT * FROM items WHERE name LIKE '%{name}%'"
        return conn.execute(query).fetchall()
