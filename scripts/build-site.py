"""Assemble the GitHub Pages build. Standard library only, no models needed.

    python scripts/build-site.py [outdir]

Takes the app's own front end, rewrites the API-backed asset paths to the
baked ones, and drops in the static-demo shim. Fixtures come from
scripts/bake-site-fixtures.py and are committed.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

SRC = Path("claimlens/static")
SITE = Path("site")
REWRITE = re.compile(r"/api/scenarios/(\w+)/image")
# The app builds one of these from a template literal.
REWRITE_TEMPLATE = re.compile(r"/api/scenarios/\$\{(\w+)\}/image")


def main(outdir: str = "dist") -> None:
    out = Path(outdir)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SRC, out)
    shutil.copytree(SITE / "fixtures", out / "fixtures")
    shutil.copytree(SITE / "assets", out / "assets")

    for path, prefix in [
        (out / "index.html", "./"),
        (out / "js" / "app.js", "./"),
        # A stylesheet resolves url() against its own directory, not the page.
        (out / "css" / "styles.css", "../"),
    ]:
        text = path.read_text()
        text = REWRITE_TEMPLATE.sub(prefix + r"assets/${\1}.jpg", text)
        text = REWRITE.sub(prefix + r"assets/\1.jpg", text)
        path.write_text(text)

    index = out / "index.html"
    html = index.read_text()
    # Shim first, so it owns fetch before the app binds anything.
    html = html.replace(
        '<script src="/static/js/app.js"></script>',
        '<script src="./js/static-mode.js"></script>\n    <script src="./js/app.js"></script>',
    )
    html = html.replace('src="/static/js/hero.js"', 'src="./js/hero.js"')
    html = html.replace('href="/static/css/styles.css"', 'href="./css/styles.css"')
    index.write_text(html)

    # Pages would otherwise treat _-prefixed paths as Jekyll internals.
    (out / ".nojekyll").write_text("")
    print(f"built {outdir}/ from {SRC} ({sum(1 for _ in out.rglob('*') if _.is_file())} files)")


if __name__ == "__main__":
    main(*sys.argv[1:])
