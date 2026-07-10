import json
import sqlite3

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType


def _connect():
    return sqlite3.connect("users.db")


def _key_str(key: StorageKey) -> str:
    return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.destiny}"


class SQLiteStorage(BaseStorage):
    # Хранит состояние диалога (FSM) в той же SQLite базе, что и остальные
    # данные бота, а не в оперативной памяти — рестарт процесса (например,
    # при деплое) больше не сбрасывает активные диалоги пользователей.
    def __init__(self):
        conn = _connect()
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fsm_storage (
            storage_key TEXT PRIMARY KEY,
            state TEXT,
            data TEXT NOT NULL DEFAULT '{}'
        )
        """)
        conn.commit()
        conn.close()

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        state_str = state.state if isinstance(state, State) else state
        conn = _connect()
        conn.execute("""
        INSERT INTO fsm_storage (storage_key, state, data) VALUES (?, ?, '{}')
        ON CONFLICT(storage_key) DO UPDATE SET state=excluded.state
        """, (_key_str(key), state_str))
        conn.commit()
        conn.close()

    async def get_state(self, key: StorageKey):
        conn = _connect()
        row = conn.execute(
            "SELECT state FROM fsm_storage WHERE storage_key=?", (_key_str(key),)
        ).fetchone()
        conn.close()
        return row[0] if row else None

    async def set_data(self, key: StorageKey, data) -> None:
        conn = _connect()
        conn.execute("""
        INSERT INTO fsm_storage (storage_key, state, data) VALUES (?, NULL, ?)
        ON CONFLICT(storage_key) DO UPDATE SET data=excluded.data
        """, (_key_str(key), json.dumps(data)))
        conn.commit()
        conn.close()

    async def get_data(self, key: StorageKey):
        conn = _connect()
        row = conn.execute(
            "SELECT data FROM fsm_storage WHERE storage_key=?", (_key_str(key),)
        ).fetchone()
        conn.close()
        return json.loads(row[0]) if row and row[0] else {}

    async def close(self) -> None:
        pass
