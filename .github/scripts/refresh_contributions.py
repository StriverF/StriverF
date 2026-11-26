"""Sync the stats card title with the rolling total on the public profile."""

from pathlib import Path
import re
from urllib.request import Request, urlopen

calendar = Request(
    "https://github.com/users/StriverF/contributions",
    headers={"Accept-Language": "en-US", "User-Agent": "StriverF-profile"},
)
with urlopen(calendar, timeout=30) as response:
    html = response.read().decode("utf-8")

heading = re.search(
    r'<h2\b[^>]*\bid="js-contribution-activity-description"[^>]*>\s*'
    r'([\d,]+)\s+contributions?\s+in the last year\s*</h2>',
    html,
)
if not heading:
    raise ValueError("GitHub did not return the rolling contribution total")

total = int(heading[1].replace(",", ""))
readme = Path("README.md")
content, matches = re.subn(
    r"(?<=custom_title=)[\d,]+(?=%20contributions%20in%20the%20last%20year)",
    f"{total:,}",
    readme.read_text(),
)
if matches != 1:
    raise ValueError("Expected one annual contribution count in the README")
readme.write_text(content)
print(f"Annual contributions: {total:,}")
