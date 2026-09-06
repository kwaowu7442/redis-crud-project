"""
features.py
-----------
Four features built on top of the loaded GitHub Archive data. These go
beyond plain CRUD to show how Redis's data structures (sorted sets,
lists, sets) make common analytics fast and simple:

1. language_popularity   - which languages take up the most code, across
                            every repo that was loaded (Redis ZSET).
2. top_watched_repos     - a "most watched" repo leaderboard (Redis ZSET).
3. commit_history        - replay a repo's commits in load order and show
                            a per-author contribution bar chart (Redis LIST).
4. author_contributions  - look up everything a specific author has
                            committed, across every repo (Redis SET).
"""

from collections import Counter


def _text_bar(value, max_value, width=30):
    """Return a simple ASCII bar proportional to value/max_value."""
    if max_value <= 0:
        return ""
    filled = int(width * value / max_value)
    return "#" * max(filled, 1 if value > 0 else 0)


def language_popularity(r, top_n=10):
    """Return the top_n programming languages by total bytes of code,
    summed across every repo that has been loaded, using the
    language:popularity ZSET that loader.py maintains."""
    results = r.zrevrange("language:popularity", 0, top_n - 1, withscores=True)
    return [(name, int(score)) for name, score in results]


def top_watched_repos(r, top_n=10):
    """Return the top_n repos by watch_count, using the
    repos:by_watchcount ZSET."""
    results = r.zrevrange("repos:by_watchcount", 0, top_n - 1, withscores=True)
    return [(name, int(score)) for name, score in results]


def license_distribution(r, top_n=10):
    """Return the top_n licenses by how many repos use them, using the
    license:distribution ZSET built from licenses.json."""
    results = r.zrevrange("license:distribution", 0, top_n - 1, withscores=True)
    return [(name, int(score)) for name, score in results]


def commit_history(r, repo_name, limit=15):
    """Return the most recent `limit` commits for a repo (in the order
    they were loaded, which follows the GitHub Archive export order),
    plus a per-author commit-count breakdown for the whole repo.

    Returns None if the repo has no commit history loaded.
    """
    commit_ids = r.lrange(f"repo:{repo_name}:commits", 0, -1)
    if not commit_ids:
        return None

    recent = []
    for commit_id in commit_ids[-limit:]:
        commit = r.hgetall(f"commit:{commit_id}")
        recent.append(
            {
                "id": commit_id[:10],
                "author": commit.get("author_name", "unknown"),
                "subject": commit.get("subject", ""),
            }
        )

    # Per-author breakdown, to visualize who contributes the most.
    author_counts = Counter()
    for commit_id in commit_ids:
        author_counts[r.hget(f"commit:{commit_id}", "author_name") or "unknown"] += 1

    top_authors = author_counts.most_common(10)
    max_count = top_authors[0][1] if top_authors else 0
    chart = [
        (author, count, _text_bar(count, max_count))
        for author, count in top_authors
    ]

    return {
        "repo_name": repo_name,
        "total_commits": len(commit_ids),
        "recent_commits": recent,
        "author_chart": chart,
    }


def author_contributions(r, author_email):
    """Return every commit made by a given author email, across all repos,
    using the author:{email} SET built at load time."""
    commit_ids = r.smembers(f"author:{author_email}")
    if not commit_ids:
        return None

    display_name = r.get(f"author:{author_email}:name") or "unknown"
    commits = []
    repo_counts = Counter()
    for commit_id in commit_ids:
        commit = r.hgetall(f"commit:{commit_id}")
        if commit:
            commits.append(
                {
                    "id": commit_id[:10],
                    "repo_name": commit.get("repo_name", "unknown"),
                    "subject": commit.get("subject", ""),
                }
            )
            repo_counts[commit.get("repo_name", "unknown")] += 1

    return {
        "author_email": author_email,
        "author_name": display_name,
        "total_commits": len(commits),
        "repos_touched": repo_counts.most_common(),
        "commits": commits,
    }
