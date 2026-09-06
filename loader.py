"""
loader.py
---------
Reads the GitHub Archive JSON-lines files bundled in ./data and stores
them in Redis using the key layout described in the README.

Each GitHub Archive export used here is one JSON object per line
(JSON Lines format), NOT a single JSON array -- so files are read
line by line and each line is parsed independently with json.loads().

Redis key layout
-----------------
repos:index                       SET      all repo_names that have been loaded
repo:{repo_name}                  HASH     watch_count, license
repo:{repo_name}:commits          LIST     commit ids, in the order they were loaded
repo:{repo_name}:files            SET      file paths seen for the repo
repo:{repo_name}:languages        HASH     language name -> bytes, for that repo
repos:by_watchcount               ZSET     repo_name -> watch_count   (leaderboard)
language:popularity               ZSET     language name -> total bytes (all repos)
license:distribution              ZSET     license name -> number of repos using it
commit:{commit_id}                HASH     repo_name, subject, message, tree, parents,
                                            author_name, author_email,
                                            committer_name, committer_email
author:{author_email}             SET      commit ids authored by that email
author:{author_email}:name        STRING   most recently seen display name for the email
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _iter_jsonl(filename):
    """Yield one parsed JSON object per line from a file in ./data."""
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_repos(r):
    """Load repos.json -> repo:{name} hash + repos:by_watchcount leaderboard."""
    count = 0
    for row in _iter_jsonl("repos.json"):
        name = row["repo_name"]
        watch_count = int(row.get("watch_count", 0))

        r.sadd("repos:index", name)
        r.hset(f"repo:{name}", mapping={"watch_count": watch_count})
        r.zadd("repos:by_watchcount", {name: watch_count})
        count += 1
    return count


def load_commits(r):
    """Load commits.json -> commit:{id} hashes, per-repo commit lists,
    and per-author commit indexes."""
    count = 0
    for row in _iter_jsonl("commits.json"):
        commit_id = row["commit"]
        repo_name = row["repo_name"]
        author = row.get("author", {}) or {}
        committer = row.get("committer", {}) or {}
        parents = row.get("parent", []) or []

        r.sadd("repos:index", repo_name)
        r.hset(
            f"commit:{commit_id}",
            mapping={
                "repo_name": repo_name,
                "subject": row.get("subject", ""),
                "message": row.get("message", ""),
                "tree": row.get("tree", ""),
                "parents": ",".join(parents),
                "author_name": author.get("name", "unknown"),
                "author_email": author.get("email", "unknown"),
                "committer_name": committer.get("name", "unknown"),
                "committer_email": committer.get("email", "unknown"),
            },
        )

        # Preserve load order so we can later "replay" a repo's history.
        r.rpush(f"repo:{repo_name}:commits", commit_id)

        # Index commits by author so we can answer "what has author X done".
        author_email = author.get("email", "unknown")
        r.sadd(f"author:{author_email}", commit_id)
        r.set(f"author:{author_email}:name", author.get("name", "unknown"))

        count += 1
    return count


def load_files(r):
    """Load files.json -> repo:{name}:files sets."""
    count = 0
    for row in _iter_jsonl("files.json"):
        r.sadd(f"repo:{row['repo_name']}:files", row["path"])
        r.sadd("repos:index", row["repo_name"])
        count += 1
    return count


def load_languages(r):
    """Load languages.json -> per-repo language hash + a global
    language:popularity leaderboard (summed bytes across all repos)."""
    count = 0
    for row in _iter_jsonl("languages.json"):
        repo_name = row["repo_name"]
        r.sadd("repos:index", repo_name)
        for lang in row.get("language", []):
            name = lang["name"]
            byte_count = int(lang.get("bytes", 0))
            r.hset(f"repo:{repo_name}:languages", name, byte_count)
            r.zincrby("language:popularity", byte_count, name)
            count += 1
    return count


def load_licenses(r):
    """Load licenses.json -> license:distribution ZSET (count of repos per
    license) and, where the repo happens to also be loaded, the repo's
    own `license` field."""
    count = 0
    for row in _iter_jsonl("licenses.json"):
        license_name = row["license"]
        r.zincrby("license:distribution", 1, license_name)

        repo_name = row["repo_name"]
        if r.sismember("repos:index", repo_name):
            r.hset(f"repo:{repo_name}", "license", license_name)
        count += 1
    return count


def load_all(r, flush_first=False):
    """Load every bundled dataset file into Redis and print a short summary.

    flush_first=True wipes the currently selected Redis DB first, which is
    useful for getting a clean, repeatable demo state.
    """
    if flush_first:
        r.flushdb()

    summary = {
        "repos": load_repos(r),
        "commits": load_commits(r),
        "files": load_files(r),
        "language rows": load_languages(r),
        "license rows": load_licenses(r),
    }

    # licenses.json is loaded last so it can enrich repo hashes that were
    # already created by load_repos() / load_commits() above. Any repo that
    # never got a license entry still gets a default value so reads never
    # crash on a missing field.
    for repo_name in r.smembers("repos:index"):
        r.hsetnx(f"repo:{repo_name}", "license", "unknown")
        r.hsetnx(f"repo:{repo_name}", "watch_count", 0)

    return summary


if __name__ == "__main__":
    # Allow `python loader.py` to load data on its own for quick testing.
    from redis_client import get_connection

    conn = get_connection()
    result = load_all(conn, flush_first=True)
    print("Load complete:")
    for key, value in result.items():
        print(f"  {key}: {value}")
