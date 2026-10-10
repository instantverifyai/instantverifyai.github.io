#!/usr/bin/env python3
"""Wrap the site's secondary pages in the same frame as the homepage / Why Us page.

Frame source of truth: why-us/index.html (top menu, fonts, colors, footer, chat button).
Each page keeps its own <title>/description/canonical/social tags and its own content.
Run from the repo root:  python3 _tools/site_frame.py
Originals are read from git (the pre-frame version at FRAME_BASE_REV) so re-runs are idempotent.
(_tools/ is not published: GitHub Pages' Jekyll skips folders that start with "_".)
"""
import re, subprocess, sys

FRAME_BASE_REV = "8ff8dbc"   # last commit before the frame was applied to these pages

def git_show(rev, path):
    return subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True, text=True, check=True).stdout

base = open("why-us/index.html").read()

# ---- frame pieces from Why Us -------------------------------------------------
head_start = base.index("<head>") + len("<head>")
css_end = base.index("  /* WHY US page */")
why_css = base[css_end:base.index("</style>", css_end)]
base_head = base[head_start:css_end]
PAGE_META = re.compile(r'^\s*(<title>.*</title>|<meta name="description"[^>]*>|<link rel="canonical"[^>]*>|'
                       r'<meta property="og:[^>]*>|<meta name="twitter:[^>]*>|<meta name="robots"[^>]*>)\s*$', re.M)
base_head = PAGE_META.sub("", base_head)
base_head = re.sub(r"\n{3,}", "\n\n", base_head)
nav = base[base.index('<nav class="topnav">'):base.index("</nav>", base.index('<nav class="topnav">')) + 6]
footer = base[base.index("<footer>"):base.index("</footer>") + 9]
widget = re.search(r'<script src="https://iv-site-agent[^>]*></script>', base).group(0)

DOC_CSS = """
  /* Secondary pages (site frame) */
  .page-hero{padding:128px 0 56px;}
  .page-hero h1{font-size:clamp(2rem,4.5vw,3rem);}
  .doc{padding:56px 0 80px;background:#fff;}
  .doc .wrap{max-width:820px;}
  .doc h2{font-family:"DM Sans",sans-serif;font-weight:800;font-size:1.45rem;color:var(--navy);margin:42px 0 12px;letter-spacing:-.01em;}
  .doc h3{font-weight:700;font-size:1.15rem;color:var(--navy);margin:28px 0 8px;}
  .doc p,.doc li{font-size:1.08rem;line-height:1.75;color:#2c3746;}
  .doc p{margin:0 0 16px;}
  .doc ul,.doc ol{margin:0 0 18px;padding-left:22px;}
  .doc li{margin-bottom:8px;}
  .doc a{color:var(--blue,#1f6feb);font-weight:600;}
  .doc hr{border:0;border-top:1px solid var(--rule);margin:36px 0;}
  .doc strong{color:#1a2535;}
  @media(max-width:640px){.page-hero{padding:100px 0 40px;}.doc{padding:40px 0 60px;}.doc p,.doc li{font-size:1.03rem;}}
"""

def page_meta(old):
    lines = [m.group(1) for m in PAGE_META.finditer(old[old.index("<head>"):old.index("</head>")])]
    return "\n".join(lines)

def ld_json(old):
    return "\n".join(re.findall(r'<script type="application/ld\+json">.*?</script>', old, re.S))

def frame(old, body_html, extra_css="", noindex=False):
    meta = page_meta(old)
    if noindex and 'name="robots"' not in meta:
        meta += '\n<meta name="robots" content="noindex">'
    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n" + meta + "\n" + base_head.rstrip() + "\n"
            + why_css + DOC_CSS + extra_css + "\n</style>\n" + ld_json(old) + "\n</head>\n<body>\n" + nav + "\n\n"
            + body_html + "\n\n" + footer + "\n" + widget + "\n</body>\n</html>\n")

def hero(eyebrow, title, lede):
    return ('<header class="why-hero page-hero">\n  <div class="hero-grid"></div>\n'
            '  <div class="wrap" style="position:relative;z-index:2">\n'
            f'    <div class="eyebrow">{eyebrow}</div>\n    <h1>{title}</h1>\n'
            + (f'    <p class="lead">{lede}</p>\n' if lede else "") + "  </div>\n</header>")

def doc_page(path, eyebrow):
    old = git_show(FRAME_BASE_REV, path)
    main = old[old.index("<main"):old.index("</main>")]
    main = main[main.index(">") + 1:]
    title = re.search(r"<h1>(.*?)</h1>", main, re.S).group(1).strip()
    lede_m = re.search(r'<p class="lede">(.*?)</p>', main, re.S)
    lede = lede_m.group(1).strip() if lede_m else ""
    main = re.sub(r"\s*<h1>.*?</h1>", "", main, count=1, flags=re.S)
    main = re.sub(r'\s*<p class="lede">.*?</p>', "", main, count=1, flags=re.S)
    main = re.sub(r'\s*<hr class="rule">', "", main, count=1)
    main = re.sub(r"\s*<hr\s*/?>\s*$", "", main.rstrip())
    # The live doc may have been edited after FRAME_BASE_REV (e.g. privacy-policy): take content from the CURRENT file
    # when it still has the old layout, so later edits aren't lost.
    cur = open(path).read()
    if '<main class="wrap">' in cur:
        cm = cur[cur.index("<main"):cur.index("</main>")]
        cm = cm[cm.index(">") + 1:]
        lede_c = re.search(r'<p class="lede">(.*?)</p>', cm, re.S)
        lede = lede_c.group(1).strip() if lede_c else lede
        cm = re.sub(r"\s*<h1>.*?</h1>", "", cm, count=1, flags=re.S)
        cm = re.sub(r'\s*<p class="lede">.*?</p>', "", cm, count=1, flags=re.S)
        cm = re.sub(r'\s*<hr class="rule">', "", cm, count=1)
        main = re.sub(r"\s*<hr\s*/?>\s*$", "", cm.rstrip())
        old = cur
    body = hero(eyebrow, title, lede) + '\n\n<main class="doc">\n  <div class="wrap">\n' + main.strip() + "\n  </div>\n</main>"
    open(path, "w").write(frame(old, body))
    print("framed", path)

def scope_css(css, scope):
    """Prefix every selector with `scope ` (handles @media blocks); :root/body become the scope itself."""
    out, i = [], 0
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    while i < len(css):
        j = css.find("{", i)
        if j == -1: break
        sel = css[i:j].strip()
        if sel.startswith("@media"):
            depth, k = 1, j + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(css[k], 0); k += 1
            out.append(sel + "{" + scope_css(css[j + 1:k - 1], scope) + "}")
            i = k; continue
        k = css.index("}", j)
        rule = css[j:k + 1]
        sels = []
        for s in sel.split(","):
            s = s.strip()
            if s in (":root", "html", "body", "*", "*,*::before,*::after"):
                sels.append(scope)
            elif s.startswith(("body ", "html ")):
                sels.append(scope + " " + s.split(" ", 1)[1])
            else:
                sels.append(scope + " " + s)
        out.append(",".join(sels) + rule)
        i = k + 1
    return "\n".join(out)

def sample_report():
    path = "sample-report/index.html"
    old = git_show(FRAME_BASE_REV, path)
    legacy = old[old.index("<style>") + 7:old.index("</style>")]
    body = old[old.index("<body>") + 6:old.index("</body>")]
    body = re.sub(r"<nav>.*?</nav>", "", body, count=1, flags=re.S)
    body = body.replace("<p>Lock founding pricing while it's open.</p>", "<p>Claim the Charter Practice Rate while spots remain.</p>")
    body = body.replace('<a href="/#start" class="btn">See founding pricing →</a>', '<a href="/#signup" class="btn" data-cta="report_claim_rate">Claim your Charter Practice Rate →</a>')
    css = "\n  /* Sample report (legacy styles, scoped) */\n  .sr{padding-top:110px !important;}\n  .sr h1,.sr h2{font-family:\"DM Sans\",sans-serif !important;font-weight:800 !important;letter-spacing:-.02em !important;}\n  @media(max-width:640px){.sr{padding-top:88px !important;}}\n" + scope_css(legacy, ".sr")
    open(path, "w").write(frame(old, '<div class="sr">' + body.strip() + "</div>", css))
    print("framed", path)

def not_found():
    path = "404.html"
    old = git_show(FRAME_BASE_REV, path)
    body = hero("Page not found", "This page got missed.",
                "The page you're looking for doesn't exist or has moved. Everything else is right where you left it.")
    body += ('\n\n<main class="doc">\n  <div class="wrap" style="display:flex;gap:14px;flex-wrap:wrap">\n'
             '    <a class="btn btn-primary" href="/">Back to the homepage</a>\n'
             '    <a class="btn btn-ghost" href="/sample-report/" style="color:var(--navy);border-color:var(--rule)">See a real report</a>\n'
             "  </div>\n</main>")
    open(path, "w").write(frame(old, body, noindex=True))
    print("framed", path)

if __name__ == "__main__":
    doc_page("privacy-policy/index.html", "Legal")
    doc_page("terms-of-service/index.html", "Legal")
    doc_page("patient-data/index.html", "Patient data")
    sample_report()
    not_found()
