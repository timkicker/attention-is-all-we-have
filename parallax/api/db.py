"""A small connection pool on top of contract.db.connect(), which sets the session for every query."""

import queue
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pymysql

from contract.db import connect

_POOL_SIZE = 40  # one per thread of the default threadpool the sync routes run in, so no connect churn under load
_pool: queue.LifoQueue = queue.LifoQueue(maxsize=_POOL_SIZE)
_lock = threading.Lock()


def _alive(conn: pymysql.connections.Connection) -> bool:
    try:
        conn.ping(reconnect=False)  # a reconnect would lose the session settings
        return True
    except Exception:
        return False


@contextmanager
def connection() -> Iterator[pymysql.connections.Connection]:
    try:
        conn = _pool.get_nowait()
        if not _alive(conn):
            conn = connect()
    except queue.Empty:
        conn = connect()
    try:
        yield conn
    except Exception:
        conn.close()
        raise
    else:
        try:
            _pool.put_nowait(conn)
        except queue.Full:
            conn.close()


def close_all() -> None:
    with _lock:
        while True:
            try:
                _pool.get_nowait().close()
            except queue.Empty:
                return
