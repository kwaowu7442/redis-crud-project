# GitHub Archive + Redis CRUD Application

A Python command-line application that loads a slice of the GitHub
Archive dataset into a Redis database and lets a user perform CRUD
(Create, Read, Update, Delete) operations on it, plus run a few small
analyses that show off Redis's data structures.

## Team members

- *(add team member names here)*

## Description

The GitHub Archive dataset ships as several JSON-lines files: repos
(watch counts), commits, files, languages, and licenses. This
application:

1. Reads those files and loads them into Redis using structures suited
   to each kind of data (hashes for repo/commit records, sorted sets
   for leaderboards, lists for ordered commit history, sets for
   file listings and per-author commit indexes).
2. Exposes a menu-driven CLI to Create, Read, Update, and Delete repo
   records.
3. Includes four features built on top of the loaded data: language
   popularity, a "most watched" repo leaderboard, license
   distribution, per-repo commit history with a contributor
   breakdown, and lookup of a specific author's past commits.

A small (~1,900 commit, 6-repo) subset of the dataset is bundled in
`data/` so the app runs immediately without needing the full archive.

## Dependencies

- Python 3.9+
- [Redis](https://redis.io/) server (7.x used during development)
- Python package: `redis` (see `requirements.txt`)

## Setup

### 1. Install and start Redis

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo service redis-server start
```

**macOS (Homebrew):**
```bash
brew install redis
brew services start redis
```

**Windows:** use [Memurai](https://www.memurai.com/) or run Redis via
WSL / Docker.

**Docker (any OS):**
```bash
docker run -d --name redis -p 6379:6379 redis:7
```

Verify it's running:
```bash
redis-cli ping
# should print: PONG
```

### 2. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the application

```bash
python main.py
```

On first run, choose option **1) Load sample data into Redis** from
the main menu before using the CRUD or Features menus.

Optional environment variables (if Redis isn't on localhost:6379):
```bash
export REDIS_HOST=your-host
export REDIS_PORT=6380
export REDIS_DB=0
```

## Project layout

```
github-redis-crud/
├── main.py             CLI menus (entry point)
├── redis_client.py     Redis connection setup
├── loader.py           Loads data/*.json into Redis
├── crud.py             Create/Read/Update/Delete for repo records
├── features.py         Language popularity, leaderboards, commit
│                        history, author-contribution lookup
├── requirements.txt
├── data/                Bundled sample dataset (JSON-lines files)
│   ├── repos.json
│   ├── commits.json
│   ├── files.json
│   ├── languages.json
│   └── licenses.json
└── README.md
```

## Redis key design

| Key | Type | Purpose |
|---|---|---|
| `repos:index` | Set | Master list of all loaded repo names |
| `repo:{name}` | Hash | `watch_count`, `license` |
| `repo:{name}:commits` | List | Commit IDs, in load order |
| `repo:{name}:files` | Set | File paths seen for the repo |
| `repo:{name}:languages` | Hash | language → bytes, per repo |
| `repos:by_watchcount` | Sorted Set | Leaderboard of repos by watch count |
| `language:popularity` | Sorted Set | Total bytes per language, across all repos |
| `license:distribution` | Sorted Set | Repo count per license |
| `commit:{id}` | Hash | subject, message, author/committer, parents, tree |
| `author:{email}` | Set | Commit IDs authored by that email |

Hashes model structured records (like a row), sorted sets give O(log N)
ranked leaderboards for free, lists preserve commit order cheaply, and
sets provide fast membership checks and de-duplication — this is why
each data type was chosen for its particular job instead of using a
single structure for everything.

## Features

1. **Language popularity** — total bytes of code per language, summed
   across every loaded repo (`ZINCRBY` at load time, `ZREVRANGE` to
   read).
2. **Most-watched repos leaderboard** — repos ranked by `watch_count`.
3. **License distribution** — how many repos in the dataset use each
   license.
4. **Commit history for a repo** — replays a repo's most recent
   commits and shows a text bar chart of top contributors by commit
   count.
5. **A user's previous contributions** — given an author's email,
   lists every commit they made and which repos they touched.

## Current status / next goals

- Loads a manageable demo subset (6 repos, ~1,900 commits) rather than
  the full multi-hundred-MB archive; swapping in the full files only
  requires pointing `loader.py` at them (memory/time permitting).
- Repo `license` field is only populated when the repo also appears in
  `licenses.json`; otherwise it defaults to `"unknown"`.
- Possible next steps: add unit tests, support loading directly from
  the original (un-filtered) GitHubArchive-Dataset.zip files, add a
  simple matplotlib chart export for the analysis features.
