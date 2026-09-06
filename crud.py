"""
crud.py
-------
Create, Read, Update, and Delete operations for repository records
stored in Redis. This is the part of the program that satisfies the
"perform CRUD operations on the data" requirement.

A repo record is made up of several Redis keys (see loader.py for the
full key layout):
    repo:{name}              HASH  watch_count, license
    repo:{name}:commits      LIST  commit ids
    repo:{name}:files        SET   file paths
    repo:{name}:languages    HASH  language -> bytes
    repos:by_watchcount      ZSET  leaderboard, kept in sync on writes
    repos:index              SET   master list of known repo names

Every function below returns plain Python values (dict / list / bool)
so the CLI layer never has to know about Redis-specific types.
"""


def create_repo(r, repo_name, watch_count=0, license="unknown"):
    """Create a new repo record. Returns False if the repo already exists."""
    if r.sismember("repos:index", repo_name):
        return False

    r.sadd("repos:index", repo_name)
    r.hset(f"repo:{repo_name}", mapping={"watch_count": watch_count, "license": license})
    r.zadd("repos:by_watchcount", {repo_name: watch_count})
    return True


def read_repo(r, repo_name):
    """Return a dict describing a repo, or None if it doesn't exist.

    Combines several Redis keys into one convenient record: the repo
    hash, its language breakdown, how many files/commits are on file,
    and its most recent commits.
    """
    if not r.sismember("repos:index", repo_name):
        return None

    data = r.hgetall(f"repo:{repo_name}")
    languages = r.hgetall(f"repo:{repo_name}:languages")
    file_count = r.scard(f"repo:{repo_name}:files")
    commit_ids = r.lrange(f"repo:{repo_name}:commits", 0, -1)

    recent_commits = []
    for commit_id in commit_ids[-5:]:
        commit = r.hgetall(f"commit:{commit_id}")
        if commit:
            recent_commits.append({"id": commit_id, **commit})

    return {
        "repo_name": repo_name,
        "watch_count": int(data.get("watch_count", 0)),
        "license": data.get("license", "unknown"),
        "languages": languages,
        "file_count": file_count,
        "commit_count": len(commit_ids),
        "recent_commits": recent_commits,
    }


def update_repo(r, repo_name, watch_count=None, license=None):
    """Update one or more fields of an existing repo. Returns False if the
    repo doesn't exist. Keeps the watch-count leaderboard in sync."""
    if not r.sismember("repos:index", repo_name):
        return False

    if watch_count is not None:
        r.hset(f"repo:{repo_name}", "watch_count", watch_count)
        r.zadd("repos:by_watchcount", {repo_name: watch_count})

    if license is not None:
        r.hset(f"repo:{repo_name}", "license", license)

    return True


def delete_repo(r, repo_name):
    """Delete a repo and everything nested under it (commits, files,
    languages). Returns False if the repo didn't exist."""
    if not r.sismember("repos:index", repo_name):
        return False

    # Delete the commit hashes that belong only to this repo before
    # dropping the list that points to them.
    commit_ids = r.lrange(f"repo:{repo_name}:commits", 0, -1)
    for commit_id in commit_ids:
        r.delete(f"commit:{commit_id}")

    r.delete(f"repo:{repo_name}")
    r.delete(f"repo:{repo_name}:commits")
    r.delete(f"repo:{repo_name}:files")
    r.delete(f"repo:{repo_name}:languages")
    r.zrem("repos:by_watchcount", repo_name)
    r.srem("repos:index", repo_name)
    return True


def list_repos(r):
    """Return a list of (repo_name, watch_count) tuples, most-watched first."""
    return r.zrevrange("repos:by_watchcount", 0, -1, withscores=True)
