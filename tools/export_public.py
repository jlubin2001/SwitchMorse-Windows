# export_public.py - make the clean public copy of this project.
#
#   python tools\export_public.py TARGET_FOLDER [--exclude PATH ...] [--ignore LINE ...]
#
# Copies every file git tracks here (as last committed) into TARGET_FOLDER,
# leaving out the --exclude paths (e.g. PLAN.md, a personal map), adds the
# --ignore lines to the public .gitignore, then commits in TARGET_FOLDER (its
# own git repository, with its own history). Pushing is left to you.
#
# Before committing, every exported text file is checked against a list of
# private words kept OUTSIDE the project, in %APPDATA%\SwitchMorse\publish_guard.txt
# (one word per line; # starts a note). If any is found the export stops and
# says where. LICENSE is not checked (it carries the author's name on purpose).
import os
import shutil
import subprocess
import sys
import time

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(os.environ.get("APPDATA", ""), "SwitchMorse", "publish_guard.txt")


def git(*args, cwd=SRC):
    return subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True,
                          encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    target = os.path.abspath(sys.argv[1])
    args = sys.argv[2:]
    exclude, ignore = set(), []
    while args:
        flag = args.pop(0)
        if flag == "--exclude":
            exclude.add(args.pop(0).replace("\\", "/"))
        elif flag == "--ignore":
            ignore.append(args.pop(0))
    if git("status", "--porcelain").stdout.strip():
        print("STOPPED: commit your changes first (the export takes the committed files).")
        return 1
    if not os.path.exists(GUARD):
        print("STOPPED: no private-word list at %s" % GUARD)
        return 1
    words = [w.strip().lower() for w in open(GUARD, encoding="utf-8")
             if w.strip() and not w.lstrip().startswith("#")]
    allowed = ["jlubin2001"]                 # the public GitHub account name

    files = [f for f in git("ls-files").stdout.splitlines() if f and f not in exclude]
    problems = []
    for f in files:
        if os.path.basename(f) == "LICENSE":
            continue
        path = os.path.join(SRC, f)
        try:
            text = open(path, encoding="utf-8").read().lower()
        except (UnicodeDecodeError, OSError):
            continue                          # binary file
        for a in allowed:
            text = text.replace(a, "")
        for w in words:
            if w in text:
                line = text[:text.index(w)].count("\n") + 1
                problems.append("%s line %d: '%s'" % (f, line, w))
    if problems:
        print("STOPPED - private words found:")
        for p in problems:
            print("  ", p)
        return 1

    os.makedirs(target, exist_ok=True)
    for name in os.listdir(target):           # start clean, keep its own .git
        if name == ".git":
            continue
        p = os.path.join(target, name)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    for f in files:
        dst = os.path.join(target, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(SRC, f), dst)
    if ignore:
        with open(os.path.join(target, ".gitignore"), "a", encoding="utf-8") as g:
            g.write("\n# kept private to each user\n" + "\n".join(ignore) + "\n")

    if not os.path.exists(os.path.join(target, ".git")):
        git("init", "-q", "-b", "main", cwd=target)
        git("config", "user.name", "jlubin2001", cwd=target)
        git("config", "user.email", "jlubin2001@users.noreply.github.com", cwd=target)
        git("config", "core.autocrlf", "true", cwd=target)
    git("add", "-A", cwd=target)
    if not git("status", "--porcelain", cwd=target).stdout.strip():
        print("Public copy already up to date: %s" % target)
        return 0
    sha = git("rev-parse", "--short", "HEAD").stdout.strip()
    msg = "Update %s" % time.strftime("%Y-%m-%d")
    if git("rev-parse", "--verify", "-q", "HEAD", cwd=target).returncode:
        msg = "First public version"
    r = git("commit", "-q", "-m", msg, "-m", "From the working copy at %s." % sha, cwd=target)
    if r.returncode:
        print(r.stdout, r.stderr)
        return 1
    print("Exported %d files to %s and committed: %s" % (len(files), target, msg))
    print("Push with:  git -C \"%s\" push" % target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
