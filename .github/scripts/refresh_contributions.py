"""Refresh the annual headline; use --with-private for an authenticated stats snapshot."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.request import Request, urlopen

CARD = Path("profile/activity.svg")
OWNER = "StriverF"


def annual_contributions():
    request = Request(
        f"https://github.com/users/{OWNER}/contributions",
        headers={"Accept-Language": "en-US", "User-Agent": "StriverF-profile"},
    )
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")
    heading = re.search(
        r'<h2\b[^>]*\bid="js-contribution-activity-description"[^>]*>\s*'
        r'([\d,]+)\s+contributions?\s+in the last year\s*</h2>', html
    )
    if not heading:
        raise ValueError("GitHub did not return the annual contribution count")
    return int(heading[1].replace(",", ""))


def api(*args):
    return json.loads(subprocess.check_output(["gh", "api", *args], text=True))


def authenticated_stats():
    query = """query($endCursor: String) {
      viewer {
        login
        privateAccess: repositories(first: 1, privacy: PRIVATE,
          affiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]) { totalCount }
        followers { totalCount }
        issues { totalCount }
        pullRequests { totalCount }
        contributionsCollection { totalPullRequestReviewContributions }
        repositories(first: 100, after: $endCursor, ownerAffiliations: [OWNER]) {
          nodes { stargazerCount }
          pageInfo { hasNextPage endCursor }
        }
      }
    }"""
    pages = api("graphql", "--paginate", "--slurp", "-f", f"query={query}")
    user = pages[0]["data"]["viewer"]
    if user["login"] != OWNER or not user["privateAccess"]["totalCount"]:
        raise ValueError("Private stats require the profile owner's private repository access")
    search = api("-X", "GET", "search/commits", "-f", f"q=author:{OWNER}", "-F", "per_page=1")
    if search["incomplete_results"]:
        raise ValueError("GitHub returned an incomplete commit count")
    return {
        "commits": search["total_count"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "reviews": user["contributionsCollection"]["totalPullRequestReviewContributions"],
        "followers": user["followers"]["totalCount"],
        "stars": sum(repo["stargazerCount"] for page in pages
                     for repo in page["data"]["viewer"]["repositories"]["nodes"]),
    }


def rank(stats):
    # GitHub Stats Extended, packages/core/src/calculateRank.ts (all_commits=true).
    score = (
        2 * (1 - 2 ** (-stats["commits"] / 1000))
        + 3 * (1 - 2 ** (-stats["prs"] / 50))
        + (1 - 2 ** (-stats["issues"] / 25))
        + (1 - 2 ** (-stats["reviews"] / 2))
        + 4 * stats["stars"] / (50 + stats["stars"])
        + stats["followers"] / (10 + stats["followers"])
    ) / 12
    thresholds = [(1, "S"), (12.5, "A+"), (25, "A"), (37.5, "A-"), (50, "B+"),
                  (62.5, "B"), (75, "B-"), (87.5, "C+"), (100, "C")]
    return next(label for limit, label in thresholds if 100 * (1 - score) <= limit), score


def render(total, stats):
    level, score = rank(stats)
    date = datetime.now(timezone.utc).date()
    rows = [("All-time commits", stats["commits"]), ("Pull requests", stats["prs"]),
            ("Issues opened", stats["issues"]), ("Stars earned", stats["stars"])]
    lines = []
    for index, (label, value) in enumerate(rows):
        y = 94 + index * 34
        lines.append(f'<text x="24" y="{y}">{label}</text>'
                     f'<text x="245" y="{y}" text-anchor="end">{value:,}</text>')
    metrics = "\n".join(lines)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="467" height="265" viewBox="0 0 467 265" role="img" aria-labelledby="title desc">
  <title id="title">GitHub contributions and activity rank</title>
  <desc id="desc">Totals include accessible public and private repositories. Rank {level} as of {date}.</desc>
  <rect x=".5" y=".5" width="466" height="264" rx="5" fill="#20232a" stroke="#e4e2e2"/>
  <g font-family="Segoe UI, Ubuntu, sans-serif">
    <text id="annual" x="24" y="37" fill="#61dafb" font-size="18" font-weight="600">{total:,} contributions in the last year</text>
    <path d="M24 57h419" stroke="#414852"/>
    <g fill="#e6edf3" font-size="15" font-weight="600">{metrics}</g>
    <circle cx="365" cy="136" r="44" fill="none" stroke="#344955" stroke-width="6"/>
    <circle cx="365" cy="136" r="44" fill="none" stroke="#61dafb" stroke-width="6" pathLength="100"
      stroke-dasharray="{score * 100:.2f} 100" transform="rotate(-90 365 136)" stroke-linecap="round"/>
    <text x="365" y="144" text-anchor="middle" fill="#fff" font-size="26" font-weight="700">{level}</text>
    <text x="365" y="206" text-anchor="middle" fill="#c2cbd5" font-size="13">Activity rank</text>
    <text x="24" y="243" fill="#b4bdc8" font-size="13">Public + private stats · {date}</text>
  </g>
</svg>
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-private", action="store_true")
    args = parser.parse_args()
    annual = annual_contributions()
    if args.with_private:
        svg = render(annual, authenticated_stats())
    else:
        svg, matches = re.subn(r'(?<=font-weight="600">)[\d,]+(?= contributions in the last year</text>)',
                               f"{annual:,}", CARD.read_text())
        if matches != 1:
            raise ValueError("Expected one annual headline in the stats card")
    CARD.write_text(svg)
