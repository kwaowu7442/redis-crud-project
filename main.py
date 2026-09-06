"""
main.py
-------
Menu-driven command line interface for the GitHub Archive + Redis CRUD
application. Run with:

    python main.py

See README.md for full setup instructions.
"""

import crud
import features
from loader import load_all
from redis_client import get_connection


def pause():
    input("\nPress Enter to continue...")


def print_header(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


# ---------------------------------------------------------------- CRUD menu

def menu_create(r):
    print_header("Create a repo record")
    name = input("Repo name (e.g. myuser/myproject): ").strip()
    watch_count = input("Watch count [0]: ").strip() or "0"
    license_name = input("License [unknown]: ").strip() or "unknown"

    created = crud.create_repo(r, name, watch_count=int(watch_count), license=license_name)
    if created:
        print(f"Created '{name}'.")
    else:
        print(f"'{name}' already exists. Use Update instead.")
    pause()


def menu_read(r):
    print_header("Read a repo record")
    name = input("Repo name: ").strip()
    record = crud.read_repo(r, name)

    if record is None:
        print(f"No repo named '{name}' found.")
        pause()
        return

    print(f"\nRepo:          {record['repo_name']}")
    print(f"Watch count:   {record['watch_count']}")
    print(f"License:       {record['license']}")
    print(f"Files on file: {record['file_count']}")
    print(f"Commits:       {record['commit_count']}")

    if record["languages"]:
        print("\nLanguages (bytes):")
        for lang, byte_count in sorted(
            record["languages"].items(), key=lambda kv: int(kv[1]), reverse=True
        ):
            print(f"  {lang:<18} {byte_count}")

    if record["recent_commits"]:
        print("\nMost recent commits:")
        for c in record["recent_commits"]:
            print(f"  {c['id'][:10]}  {c.get('author_name', '?'):<20} {c.get('subject', '')}")

    pause()


def menu_update(r):
    print_header("Update a repo record")
    name = input("Repo name: ").strip()

    if not crud.read_repo(r, name):
        print(f"No repo named '{name}' found.")
        pause()
        return

    watch_count = input("New watch count (leave blank to skip): ").strip()
    license_name = input("New license (leave blank to skip): ").strip()

    updated = crud.update_repo(
        r,
        name,
        watch_count=int(watch_count) if watch_count else None,
        license=license_name or None,
    )
    print("Updated." if updated else "Update failed.")
    pause()


def menu_delete(r):
    print_header("Delete a repo record")
    name = input("Repo name: ").strip()
    confirm = input(f"Type YES to permanently delete '{name}': ").strip()

    if confirm != "YES":
        print("Cancelled.")
        pause()
        return

    deleted = crud.delete_repo(r, name)
    print("Deleted." if deleted else f"No repo named '{name}' found.")
    pause()


def menu_list(r):
    print_header("All repos (by watch count)")
    repos = crud.list_repos(r)
    if not repos:
        print("No repos loaded yet. Use the Load Sample Data option first.")
    for name, watch_count in repos:
        print(f"  {name:<30} watch_count={int(watch_count)}")
    pause()


# ------------------------------------------------------------ Feature menu

def menu_language_popularity(r):
    print_header("Feature: language popularity across all loaded repos")
    results = features.language_popularity(r, top_n=10)
    if not results:
        print("No language data loaded.")
        pause()
        return

    max_bytes = results[0][1]
    for name, byte_count in results:
        bar = "#" * max(int(30 * byte_count / max_bytes), 1)
        print(f"  {name:<16} {bar} ({byte_count:,} bytes)")
    pause()


def menu_top_watched(r):
    print_header("Feature: most-watched repos")
    for name, watch_count in features.top_watched_repos(r, top_n=10):
        print(f"  {name:<30} {watch_count:,} watchers")
    pause()


def menu_license_distribution(r):
    print_header("Feature: license distribution across the dataset")
    for name, repo_count in features.license_distribution(r, top_n=10):
        print(f"  {name:<15} used by {repo_count:,} repos")
    pause()


def menu_commit_history(r):
    print_header("Feature: commit history + contributor breakdown")
    name = input("Repo name (e.g. torvalds/linux): ").strip()
    result = features.commit_history(r, name, limit=15)

    if result is None:
        print(f"No commit history found for '{name}'.")
        pause()
        return

    print(f"\n{result['repo_name']} -- {result['total_commits']} commits loaded")
    print("\nMost recent commits:")
    for c in result["recent_commits"]:
        print(f"  {c['id']}  {c['author']:<20} {c['subject']}")

    print("\nTop contributors:")
    for author, count, bar in result["author_chart"]:
        print(f"  {author:<20} {bar} ({count})")
    pause()


def menu_author_contributions(r):
    print_header("Feature: a user's previous contributions")
    email = input("Author email (see a commit's author_email field): ").strip()
    result = features.author_contributions(r, email)

    if result is None:
        print(f"No commits found for '{email}'.")
        pause()
        return

    print(f"\n{result['author_name']} <{result['author_email']}>")
    print(f"Total commits: {result['total_commits']}")
    print("\nRepos touched:")
    for repo_name, count in result["repos_touched"]:
        print(f"  {repo_name:<30} {count} commit(s)")

    print("\nSample commits:")
    for c in result["commits"][:10]:
        print(f"  {c['id']}  {c['repo_name']:<20} {c['subject']}")
    pause()


# ------------------------------------------------------------------- menus

CRUD_MENU = """
--- CRUD ---
1) Create a repo
2) Read a repo
3) Update a repo
4) Delete a repo
5) List all repos
0) Back
"""

FEATURE_MENU = """
--- Features ---
1) Language popularity
2) Most-watched repos leaderboard
3) License distribution
4) Commit history for a repo
5) A user's previous contributions
0) Back
"""

MAIN_MENU = """
==================================================
 GitHub Archive + Redis CRUD Application
==================================================
1) Load sample data into Redis (safe to re-run)
2) CRUD operations
3) Features / analysis
0) Exit
"""


def crud_menu(r):
    actions = {
        "1": menu_create,
        "2": menu_read,
        "3": menu_update,
        "4": menu_delete,
        "5": menu_list,
    }
    while True:
        print(CRUD_MENU)
        choice = input("Choose an option: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if action:
            action(r)
        else:
            print("Invalid option.")


def feature_menu(r):
    actions = {
        "1": menu_language_popularity,
        "2": menu_top_watched,
        "3": menu_license_distribution,
        "4": menu_commit_history,
        "5": menu_author_contributions,
    }
    while True:
        print(FEATURE_MENU)
        choice = input("Choose an option: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if action:
            action(r)
        else:
            print("Invalid option.")


def main():
    r = get_connection()

    while True:
        print(MAIN_MENU)
        choice = input("Choose an option: ").strip()

        if choice == "1":
            print("Loading sample data (this clears the current database first)...")
            summary = load_all(r, flush_first=True)
            for key, value in summary.items():
                print(f"  {key}: {value}")
            pause()
        elif choice == "2":
            crud_menu(r)
        elif choice == "3":
            feature_menu(r)
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()
