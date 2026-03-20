# app.py — Digital Footprint Visualizer (Full Version)

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
CORS(app)


# ══════════════════════════════════════════════
#  PLATFORM CHECKERS
#  Each returns a dict with at least {"found": True/False}
# ══════════════════════════════════════════════

def check_github(username):
    """GitHub public API — no key needed."""
    try:
        url = f"https://api.github.com/users/{username}"
        r = requests.get(url, headers={"User-Agent": "DigitalFootprintApp"}, timeout=5)
        if r.status_code == 200:
            d = r.json()
            return {
                "found": True,
                "url": f"https://github.com/{username}",
                "display_name": d.get("name") or username,
                "bio": d.get("bio") or "",
                "followers": d.get("followers", 0),
                "public_repos": d.get("public_repos", 0),
            }
    except requests.RequestException:
        pass
    return {"found": False}


def check_reddit(username):
    """Reddit public JSON API — no key needed."""
    try:
        url = f"https://www.reddit.com/user/{username}/about.json"
        r = requests.get(url, headers={"User-Agent": "DigitalFootprintApp/1.0"}, timeout=5)
        if r.status_code == 200:
            d = r.json().get("data", {})
            return {
                "found": True,
                "url": f"https://www.reddit.com/user/{username}",
                "display_name": d.get("name") or username,
                "bio": d.get("subreddit", {}).get("public_description") or "",
                "karma": d.get("total_karma", 0),
            }
    except requests.RequestException:
        pass
    return {"found": False}


def check_npm(username):
    """npm registry public API — checks if a username has published packages."""
    try:
        url = f"https://registry.npmjs.org/-/v1/search?text=maintainer:{username}&size=5"
        r = requests.get(url, headers={"User-Agent": "DigitalFootprintApp"}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            total = data.get("total", 0)
            if total > 0:
                return {
                    "found": True,
                    "url": f"https://www.npmjs.com/~{username}",
                    "display_name": username,
                    "bio": f"{total} package(s) published",
                    "packages": total,
                }
    except requests.RequestException:
        pass
    return {"found": False}


def check_hackernews(username):
    """HackerNews public API."""
    try:
        url = f"https://hacker-news.firebaseio.com/v0/user/{username}.json"
        r = requests.get(url, headers={"User-Agent": "DigitalFootprintApp"}, timeout=5)
        if r.status_code == 200 and r.json() is not None:
            d = r.json()
            return {
                "found": True,
                "url": f"https://news.ycombinator.com/user?id={username}",
                "display_name": d.get("id") or username,
                "bio": d.get("about") or "",
                "karma": d.get("karma", 0),
            }
    except requests.RequestException:
        pass
    return {"found": False}


def check_devto(username):
    """Dev.to public API — no key needed."""
    try:
        url = f"https://dev.to/api/users/by_username?url={username}"
        r = requests.get(url, headers={"User-Agent": "DigitalFootprintApp"}, timeout=5)
        if r.status_code == 200:
            d = r.json()
            return {
                "found": True,
                "url": f"https://dev.to/{username}",
                "display_name": d.get("name") or username,
                "bio": d.get("summary") or "",
                "followers": d.get("followers_count", 0),
            }
    except requests.RequestException:
        pass
    return {"found": False}


def check_gitlab(username):
    """GitLab official public API — no key needed for public profiles."""
    try:
        url = f"https://gitlab.com/api/v4/users?username={username}"
        r = requests.get(url, headers={"User-Agent": "DigitalFootprintApp"}, timeout=5)
        if r.status_code == 200:
            users = r.json()
            if users and len(users) > 0:
                d = users[0]
                return {
                    "found": True,
                    "url": d.get("web_url", f"https://gitlab.com/{username}"),
                    "display_name": d.get("name") or username,
                    "bio": d.get("bio") or "",
                    "followers": d.get("followers", 0),
                }
    except requests.RequestException:
        pass
    return {"found": False}


def check_pypi(username):
    """PyPI — checks if username has a user profile or published packages."""
    try:
        # First try direct user profile page
        url = f"https://pypi.org/user/{username}/"
        r = requests.get(url, headers={"User-Agent": "DigitalFootprintApp"}, timeout=5)
        if r.status_code == 200:
            return {
                "found": True,
                "url": url,
                "display_name": username,
                "bio": "PyPI user profile found",
            }
        # Fallback: try username as a package name
        url2 = f"https://pypi.org/pypi/{username}/json"
        r2 = requests.get(url2, headers={"User-Agent": "DigitalFootprintApp"}, timeout=5)
        if r2.status_code == 200:
            d = r2.json().get("info", {})
            return {
                "found": True,
                "url": f"https://pypi.org/project/{username}",
                "display_name": d.get("author") or username,
                "bio": d.get("summary") or "",
            }
    except requests.RequestException:
        pass
    return {"found": False}




def check_twitter(username):
    """
    Twitter/X blocks automated checks aggressively.
    We provide a manual check link instead.
    """
    return {
        "found": None,
        "manual": True,
        "url": f"https://twitter.com/{username}",
        "display_name": username,
        "bio": "",
        "note": "Twitter/X blocks automated checks — click to verify.",
    }


def check_instagram(username):
    """
    Instagram blocks all automated requests.
    We provide a manual check link instead.
    """
    return {
        "found": None,
        "manual": True,
        "url": f"https://instagram.com/{username}",
        "display_name": username,
        "bio": "",
        "note": "Instagram blocks automated checks — click to verify.",
    }


def check_linkedin(username):
    """
    LinkedIn blocks all automated requests.
    We provide a manual check link instead.
    """
    return {
        "found": None,
        "manual": True,
        "url": f"https://www.linkedin.com/in/{username}",
        "display_name": username,
        "bio": "",
        "note": "LinkedIn blocks automated checks — click to verify manually.",
    }


# ══════════════════════════════════════════════
#  BIO ANALYSER
# ══════════════════════════════════════════════

INTEREST_KEYWORDS = {
    "languages": [
        "python", "javascript", "typescript", "rust", "go", "golang",
        "java", "kotlin", "swift", "c++", "c#", "ruby", "php", "scala",
        "haskell", "elixir", "clojure", "dart", "lua", "r", "matlab",
        "bash", "shell", "powershell", "sql", "html", "css", "solidity",
        "perl", "groovy", "assembly", "fortran", "cobol", "vba",
    ],
    "topics": [
        "web", "backend", "frontend", "fullstack", "full-stack",
        "machine learning", "ml", "ai", "deep learning", "nlp",
        "data science", "data", "analytics", "blockchain", "crypto",
        "security", "cybersecurity", "devops", "cloud", "linux",
        "open source", "opensource", "mobile", "ios", "android",
        "gaming", "game", "graphics", "embedded", "iot", "robotics",
        "networking", "distributed", "systems", "compiler", "algorithms",
        "privacy", "automation", "testing", "api", "databases",
        "photography", "music", "design", "art", "writing", "science",
        "finance", "trading", "math", "physics", "biology", "chemistry",
    ],
    "tools": [
        "react", "vue", "angular", "svelte", "nextjs", "next.js",
        "node", "nodejs", "express", "django", "flask", "fastapi",
        "rails", "spring", "laravel", "tensorflow", "pytorch", "keras",
        "docker", "kubernetes", "k8s", "aws", "gcp", "azure",
        "postgres", "postgresql", "mysql", "mongodb", "redis",
        "graphql", "rest", "grpc", "git", "github", "linux",
        "nginx", "terraform", "ansible", "jenkins", "ci/cd",
        "vscode", "vim", "neovim", "figma", "wordpress", "shopify",
        "pandas", "numpy", "scipy", "sklearn", "jupyter", "excel",
    ],
    "soft_skills": [
        "mentor", "mentoring", "teaching", "speaker", "writing",
        "blogger", "author", "consultant", "freelance", "freelancer",
        "founder", "co-founder", "cto", "engineer", "developer",
        "researcher", "student", "learner", "contributor", "community",
        "leader", "manager", "architect", "designer", "passionate",
        "enthusiast", "hobbyist", "maker", "hacker", "tinkerer",
        "dad", "mom", "parent", "husband", "wife", "human",
        "coffee", "tea", "reader", "traveler", "runner", "gamer",
    ],
}


def analyze_bios(platforms):
    """Collect bios from all found platforms and extract interest keywords."""
    all_bio_text = []
    for platform_data in platforms.values():
        bio = platform_data.get("bio", "")
        if bio and platform_data.get("found"):
            all_bio_text.append(bio)

    combined = " ".join(all_bio_text).lower()
    found_interests = {category: [] for category in INTEREST_KEYWORDS}

    for category, keywords in INTEREST_KEYWORDS.items():
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, combined):
                found_interests[category].append(keyword)

    total = sum(len(v) for v in found_interests.values())

    return {
        "bios_collected": all_bio_text,
        "interests": found_interests,
        "total_keywords_found": total,
        "has_data": total > 0,
    }


# ══════════════════════════════════════════════
#  TRACEABILITY SCORER
# ══════════════════════════════════════════════

def calculate_score(platforms):
    score = 0
    reasons = []

    # These platforms can't be auto-checked — skip from scoring
    MANUAL_PLATFORMS = {"linkedin", "twitter", "instagram"}

    for platform, data in platforms.items():
        if platform in MANUAL_PLATFORMS:
            continue
        if data.get("found"):
            score += 20
            reasons.append(f"Found on {platform.capitalize()}")

    # Bonus points
    gh = platforms.get("github", {})
    if gh.get("found"):
        if gh.get("followers", 0) > 10:
            score += 10
            reasons.append(f"GitHub: {gh.get('followers')} followers")
        if gh.get("bio"):
            score += 5
            reasons.append("GitHub: has a public bio")
        if gh.get("public_repos", 0) > 3:
            score += 5
            reasons.append(f"GitHub: {gh.get('public_repos')} public repos")

    rd = platforms.get("reddit", {})
    if rd.get("found") and rd.get("karma", 0) > 100:
        score += 5
        reasons.append(f"Reddit: {rd.get('karma')} karma")

    hn = platforms.get("hackernews", {})
    if hn.get("found") and hn.get("karma", 0) > 50:
        score += 5
        reasons.append(f"HackerNews: {hn.get('karma')} karma")

    dv = platforms.get("devto", {})
    if dv.get("found") and dv.get("followers", 0) > 5:
        score += 5
        reasons.append(f"Dev.to: {dv.get('followers')} followers")

    score = min(score, 100)

    if score < 30:
        label = "LOW"
        description = "This username has a minimal public footprint. Hard to trace."
    elif score < 60:
        label = "MEDIUM"
        description = "This username has a moderate public presence."
    else:
        label = "HIGH"
        description = "This username is highly traceable across the web."

    return {
        "score": score,
        "label": label,
        "description": description,
        "reasons": reasons,
    }


# ══════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ui")
def ui():
    return render_template("index.html")


@app.route("/check")
def check_username():
    username = request.args.get("username", "").strip()

    if not username:
        return jsonify({"error": "Please provide a username"}), 400

    if len(username) < 1 or len(username) > 50:
        return jsonify({"error": "Username must be between 1 and 50 characters"}), 400

    print(f"[CHECK] Searching for username: {username}")

    # ── Parallel platform checks ──
    # All 11 platforms checked simultaneously.
    # Total wait = slowest single platform, not sum of all.
    CHECKERS = {
        "github":    lambda: check_github(username),
        "reddit":    lambda: check_reddit(username),
        "npm":       lambda: check_npm(username),
        "hackernews":lambda: check_hackernews(username),
        "devto":     lambda: check_devto(username),
        "gitlab":    lambda: check_gitlab(username),
        "pypi":      lambda: check_pypi(username),
        "twitter":   lambda: check_twitter(username),
        "instagram": lambda: check_instagram(username),
        "linkedin":  lambda: check_linkedin(username),
    }

    platforms = {}

    # max_workers=11 — one thread per platform
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_platform = {
            executor.submit(fn): name
            for name, fn in CHECKERS.items()
        }
        for future in as_completed(future_to_platform):
            platform_name = future_to_platform[future]
            try:
                platforms[platform_name] = future.result()
            except Exception as e:
                print(f"[ERROR] {platform_name} check failed: {e}")
                platforms[platform_name] = {"found": False}

    # Restore consistent display order
    PLATFORM_ORDER = [
        "github", "gitlab", "reddit", "npm", "hackernews",
        "devto", "pypi", "twitter", "instagram", "linkedin"
    ]
    platforms = {k: platforms[k] for k in PLATFORM_ORDER if k in platforms}

    traceability = calculate_score(platforms)
    bio_analysis = analyze_bios(platforms)

    return jsonify({
        "username": username,
        "platforms": platforms,
        "traceability": traceability,
        "bio_analysis": bio_analysis,
    })


if __name__ == "__main__":
    app.run(debug=True)