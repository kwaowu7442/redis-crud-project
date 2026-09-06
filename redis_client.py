"""
redis_client.py
----------------
Single place responsible for creating and returning a Redis connection.
Every other module imports `get_connection()` from here instead of
calling `redis.Redis(...)` directly, so connection settings only need
to change in one place.

Connection settings can be overridden with environment variables:
    REDIS_HOST (default: "localhost")
    REDIS_PORT (default: 6379)
    REDIS_DB   (default: 0)
"""

import os
import redis


def get_connection():
    """Create and return a Redis connection using environment variables
    (with sensible localhost defaults) and verify it is reachable.
    """
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", 6379))
    db = int(os.getenv("REDIS_DB", 0))

    # decode_responses=True means Redis returns normal Python strings
    # instead of bytes, which keeps the rest of the code much simpler.
    connection = redis.Redis(host=host, port=port, db=db, decode_responses=True)

    try:
        connection.ping()
    except redis.exceptions.ConnectionError as exc:
        raise SystemExit(
            f"Could not connect to Redis at {host}:{port} (db {db}).\n"
            "Make sure a Redis server is running -- see the README for setup "
            "instructions.\n"
            f"Original error: {exc}"
        )

    return connection
