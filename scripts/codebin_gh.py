"""
GitHub CLI & Remote Integration for CodeBin.
Provides commands to clone and index remote GitHub repositories,
manage local git repositories, create remotes, and synchronize binary indices.
Zero external dependencies (uses standard library urllib & subprocess).
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from codebin_engine import CodeBinManager


def run_git_cmd(args: list, cwd: str = ".") -> Tuple_output := Tuple[int, str, str]:
    """Runs a git command safely and captures output."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except FileNotFoundError:
        return -1, "", "Git executable not found in PATH."


def gh_clone_and_index(repo_url: str, target_dir: Optional[str] = None, depth: int = 1) -> bool:
    """Clones a GitHub repository and immediately indexes its symbols."""
    # Normalize repo_url (e.g., 'owner/repo' -> 'https://github.com/owner/repo.git')
    if not repo_url.startswith(("http://", "https://", "git@")):
        repo_url = f"https://github.com/{repo_url}.git"

    if not target_dir:
        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        target_dir = os.path.abspath(repo_name)

    print(f"📦 Cloning {repo_url} into {target_dir} (depth={depth})...")
    code, stdout, stderr = run_git_cmd(["clone", "--depth", str(depth), repo_url, target_dir])
    if code != 0:
        print(f"❌ Git clone failed: {stderr}")
        return False

    print("⚡ Building CodeBin binary symbol index...")
    mgr = CodeBinManager(target_dir)
    stats = mgr.scan()
    print(f"✅ Indexed {stats['added']} symbols in {target_dir}/.codebin/symbols.bin")
    return True


def gh_create_remote_repo(
    repo_name: str,
    token: Optional[str] = None,
    private: bool = False,
    description: str = "CodeBin: High-performance binary codebase symbol cache and indexer",
) -> Optional[str]:
    """Creates a repository on GitHub using the REST API."""
    auth_token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not auth_token:
        print("⚠️ No GITHUB_TOKEN found in environment. Cannot create remote repository via API.")
        print("💡 Create the repo manually at https://github.com/new or export GITHUB_TOKEN=your_token.")
        return None

    url = "https://api.github.com/user/repos"
    payload = json.dumps({
        "name": repo_name,
        "description": description,
        "private": private,
        "auto_init": False,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {auth_token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "CodeBin-CLI",
    })

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            clone_url = data.get("clone_url")
            print(f"✅ Successfully created GitHub repository: {data.get('html_url')}")
            return clone_url
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        if e.code == 422 and "already exists" in err_body:
            print(f"ℹ️ Repository '{repo_name}' already exists on your GitHub account.")
            return f"https://github.com/{data.get('owner', {}).get('login', 'user')}/{repo_name}.git"
        print(f"❌ Failed to create repository (HTTP {e.code}): {err_body}")
        return None
    except Exception as e:
        print(f"❌ Network error while creating repository: {e}")
        return None


def gh_init_and_commit(
    project_dir: str = ".",
    commit_msg: str = "Initial commit: CodeBin universal codebase indexer and AI skill",
    remote_url: Optional[str] = None,
) -> bool:
    """Initializes local git repository, creates initial commit, and attaches remote."""
    cwd = os.path.abspath(project_dir)

    # 1. git init
    code, out, err = run_git_cmd(["init", "-b", "main"], cwd=cwd)
    if code != 0:
        # Fallback for older git versions without -b
        run_git_cmd(["init"], cwd=cwd)
        run_git_cmd(["checkout", "-b", "main"], cwd=cwd)

    # 2. Stage all files
    code, out, err = run_git_cmd(["add", "."], cwd=cwd)
    if code != 0:
        print(f"❌ git add failed: {err}")
        return False

    # 3. Commit
    code, out, err = run_git_cmd(["commit", "-m", commit_msg], cwd=cwd)
    if code == 0:
        print(f"✅ Created commit: {commit_msg}")
    elif "nothing to commit" in out or "nothing to commit" in err:
        print("ℹ️ Working directory clean, nothing to commit.")
    else:
        print(f"⚠️ git commit notice: {out or err}")

    # 4. Attach remote if provided
    if remote_url:
        run_git_cmd(["remote", "remove", "origin"], cwd=cwd)
        code, out, err = run_git_cmd(["remote", "add", "origin", remote_url], cwd=cwd)
        if code == 0:
            print(f"✅ Attached remote origin: {remote_url}")

    return True


def gh_push(project_dir: str = ".", branch: str = "main") -> bool:
    """Pushes local commits to the remote origin."""
    cwd = os.path.abspath(project_dir)
    print(f"🚀 Pushing to origin/{branch}...")
    code, out, err = run_git_cmd(["push", "-u", "origin", branch], cwd=cwd)
    if code == 0:
        print(f"✅ Successfully pushed to origin/{branch}!")
        return True
    else:
        print(f"❌ Git push failed: {err or out}")
        return False


def main():
    parser = argparse.ArgumentParser(description="CodeBin GitHub CLI Integration")
    sub = parser.add_subparsers(dest="cmd", help="GitHub subcommand")

    # clone-index
    clone_p = sub.add_parser("clone-index", help="Clone a GitHub repo and build binary index")
    clone_p.add_argument("repo", help="GitHub repo (e.g. owner/repo or https://github.com/...)")
    clone_p.add_argument("target", nargs="?", default=None, help="Target directory")

    # init-repo
    init_p = sub.add_parser("init-repo", help="Initialize local git repo, stage files, and commit")
    init_p.add_argument("--remote", default=None, help="Remote origin URL to set")
    init_p.add_argument("-m", "--message", default="Initial commit: CodeBin codebase indexer", help="Commit message")

    # push
    push_p = sub.add_parser("push", help="Push commits to origin")
    push_p.add_argument("--branch", default="main", help="Branch name")

    # create-remote
    create_p = sub.add_parser("create-remote", help="Create a repository on GitHub via API")
    create_p.add_argument("name", help="Repository name")
    create_p.add_argument("--private", action="store_true", help="Make repository private")
    create_p.add_argument("--token", default=None, help="GitHub Personal Access Token")

    args = parser.parse_args()

    if args.cmd == "clone-index":
        gh_clone_and_index(args.repo, args.target)
    elif args.cmd == "init-repo":
        gh_init_and_commit(commit_msg=args.message, remote_url=args.remote)
    elif args.cmd == "push":
        gh_push(branch=args.branch)
    elif args.cmd == "create-remote":
        gh_create_remote_repo(args.name, token=args.token, private=args.private)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
