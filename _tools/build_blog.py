#!/usr/bin/env python3
"""Build the site's /blog/ section from the posts published on Ghost, in the site's own design.

Ghost stays where posts are written, scheduled, and emailed to the newsletter list. This script pulls the
*published* posts from Ghost's public Content API and writes:
  blog/index.html             list of posts + newsletter signup
  blog/<slug>/index.html      one page per post
and refreshes the blog URLs in sitemap.xml. Run from the repo root:  python3 _tools/build_blog.py
A GitHub Actions workflow (.github/workflows/blog.yml) runs it after each Tuesday publish.
"""
import html, json, os, re, shutil, sys, urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import site_frame as sf  # frame pieces from why-us/index.html

GHOST = "https://instantverify-ai.ghost.io"
KEY = "46a61d494a232d0fdde6749320"   # Ghost Content API key: public by design (read-only, published posts only)
SITE = "https://instantverifyai.com"

def fetch_posts():
    url = (f"{GHOST}/ghost/api/content/posts/?key={KEY}&limit=all&formats=html&order=published_at%20desc"
           "&fields=id,title,slug,html,excerpt,custom_excerpt,meta_title,meta_description,feature_image,"
           "feature_image_alt,published_at,updated_at,reading_time")
    req = urllib.request.Request(url, headers={"User-Agent": "instantverifyai-blog-builder/1.0"})
    return json.load(urllib.request.urlopen(req, timeout=60))["posts"]

def esc(s): return html.escape(s or "", quote=True)

def nice_date(iso): return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%B %-d, %Y")

def summary(p):
    return (p.get("custom_excerpt") or p.get("meta_description") or p.get("excerpt") or "").strip().replace("\n", " ")

BLOG_CSS = """
  /* Blog */
  .blog-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:24px;max-width:1100px;}
  .bcard{display:flex;flex-direction:column;background:#fff;border:1px solid var(--rule);border-radius:14px;overflow:hidden;text-decoration:none;color:inherit;transition:transform .2s,box-shadow .2s;}
  .bcard:hover{transform:translateY(-3px);box-shadow:0 14px 34px rgba(13,31,53,.12);}
  .bcard img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:var(--lgray);}
  .bcard .bc-body{padding:20px 22px 24px;}
  .bcard .bc-date{font-size:.85rem;color:var(--gray);font-weight:600;letter-spacing:.02em;}
  .bcard h2{font-family:"DM Sans",sans-serif;font-weight:800;font-size:1.25rem;line-height:1.3;color:var(--navy);margin:8px 0 10px;letter-spacing:-.01em;}
  .bcard p{font-size:1rem;line-height:1.6;color:#2c3746;margin:0;}
  .doc .wrap.blog-wrap{max-width:1100px;}
  .post-meta{color:rgba(255,255,255,.75);font-size:1rem;margin-top:14px;}
  .post-feature{max-width:820px;margin:0 auto 34px;}
  .post-feature img{width:100%;border-radius:14px;display:block;}
  .subscribe-box{background:var(--navy);color:#fff;border-radius:16px;padding:30px 32px;margin:48px 0 0;}
  .subscribe-box h3{color:#fff;font-family:"DM Sans",sans-serif;font-weight:800;font-size:1.35rem;margin:0 0 6px;}
  .subscribe-box p{color:rgba(255,255,255,.8) !important;margin:0 0 16px !important;font-size:1.02rem !important;}
  .subscribe-form{display:flex;gap:10px;flex-wrap:wrap;}
  .subscribe-form input{flex:1;min-width:220px;padding:13px 14px;border-radius:9px;border:1px solid rgba(255,255,255,.25);background:rgba(255,255,255,.08);color:#fff;font-size:1rem;}
  .subscribe-form input::placeholder{color:rgba(255,255,255,.55);}
  .subscribe-form button{padding:13px 22px;border:0;border-radius:9px;background:var(--teal);color:var(--navy);font-weight:700;font-size:1rem;cursor:pointer;}
  .subscribe-msg{margin-top:10px;font-size:.95rem;color:var(--teal);min-height:1.2em;}
  .post-cta{margin-top:36px;padding-top:28px;border-top:1px solid var(--rule);display:flex;gap:12px;flex-wrap:wrap;align-items:center;}
  .post-cta .btn-ghost{color:var(--navy);border-color:var(--rule);}
  .back-link{display:inline-block;margin-bottom:22px;font-weight:600;color:var(--blue,#1f6feb);text-decoration:none;}
  @media(max-width:640px){.subscribe-box{padding:24px 20px;}}
"""

SUBSCRIBE = """<div class="subscribe-box" id="subscribe">
      <h3>Get the Tuesday newsletter</h3>
      <p>One short email a week about dental insurance verification and front desk life. Unsubscribe anytime.</p>
      <form class="subscribe-form" onsubmit="return ivSubscribe(this)">
        <input type="email" name="email" placeholder="you@yourpractice.com" required aria-label="Email address">
        <button type="submit">Subscribe</button>
      </form>
      <div class="subscribe-msg" role="status"></div>
    </div>"""

SUBSCRIBE_JS = """<script>
  // Same flow as Ghost's own signup form: Ghost emails a confirmation link (double opt-in).
  async function ivSubscribe(form) {
    const msg = form.parentNode.querySelector('.subscribe-msg');
    const email = form.email.value.trim();
    msg.textContent = 'Sending…';
    try {
      let token = '';
      try { const t = await fetch('%(g)s/members/api/integrity-token/', { cache: 'no-store' }); if (t.ok) token = await t.text(); } catch (e) {}
      const r = await fetch('%(g)s/members/api/send-magic-link/', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, emailType: 'signup', labels: ['website-blog'], integrityToken: token }) });
      if (!r.ok) throw new Error(r.status);
      msg.textContent = 'Almost done: check your inbox for a confirmation link.';
      form.reset();
      if (typeof gtag === 'function') gtag('event', 'newsletter_signup', { method: 'website_blog' });
    } catch (e) {
      msg.innerHTML = 'Something went wrong. You can also <a href="%(g)s/#/portal/signup" style="color:#fff">subscribe here</a>.';
    }
    return false;
  }
</script>""" % {"g": GHOST}

def meta_block(title, desc, canonical, image=None, og_type="website", extra=""):
    m = [f"<title>{esc(title)}</title>", f'<meta name="description" content="{esc(desc)}">',
         f'<link rel="canonical" href="{canonical}">', f'<meta property="og:type" content="{og_type}">',
         f'<meta property="og:title" content="{esc(title)}">', f'<meta property="og:description" content="{esc(desc)}">',
         f'<meta property="og:url" content="{canonical}">',
         f'<meta property="og:image" content="{esc(image or SITE + "/og-image.jpg")}">',
         '<meta name="twitter:card" content="summary_large_image">', f'<meta name="twitter:title" content="{esc(title)}">',
         f'<meta name="twitter:description" content="{esc(desc)}">', f'<meta name="twitter:image" content="{esc(image or SITE + "/og-image.jpg")}">']
    return "<head>\n" + "\n".join(m) + "\n" + extra + "\n</head>"

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(content)

def build():
    posts = fetch_posts()
    if not posts:
        sys.exit("No published posts returned; refusing to wipe the blog.")
    # index
    cards = []
    for p in posts:
        img = f'<img src="{esc(p["feature_image"])}" alt="{esc(p.get("feature_image_alt") or "")}" loading="lazy">' if p.get("feature_image") else ""
        cards.append(f'''      <a class="bcard" href="/blog/{p["slug"]}/">
        {img}
        <div class="bc-body"><div class="bc-date">{nice_date(p["published_at"])}</div><h2>{esc(p["title"])}</h2><p>{esc(summary(p))}</p></div>
      </a>''')
    body = sf.hero("The InstantVerify blog", "Every patient, every procedure, every insight.",
                   "A new edition every Tuesday on dental insurance verification, estimates, and front desk life.")
    body += ('\n\n<main class="doc">\n  <div class="wrap blog-wrap">\n    <div class="blog-list">\n' + "\n".join(cards)
             + "\n    </div>\n    <div style=\"max-width:820px\">" + SUBSCRIBE + "</div>\n  </div>\n</main>\n" + SUBSCRIBE_JS)
    head = meta_block("Blog | InstantVerify AI", "Weekly articles on dental insurance verification, accurate estimates, and running a calmer front desk.",
                      SITE + "/blog/")
    write("blog/index.html", sf.frame(head, body, BLOG_CSS))
    # posts
    keep = {"index.html"}
    for p in posts:
        keep.add(p["slug"])
        desc = summary(p)[:300]
        canonical = f"{SITE}/blog/{p['slug']}/"
        ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"], "description": desc,
              "datePublished": p["published_at"], "dateModified": p.get("updated_at") or p["published_at"],
              "mainEntityOfPage": canonical, "author": {"@type": "Organization", "name": "InstantVerify AI"},
              "publisher": {"@type": "Organization", "name": "InstantVerify AI", "logo": {"@type": "ImageObject", "url": SITE + "/apple-touch-icon.png"}}}
        if p.get("feature_image"): ld["image"] = p["feature_image"]
        extra = '<script type="application/ld+json">' + json.dumps(ld) + "</script>"
        head = meta_block(f'{p.get("meta_title") or p["title"]} | InstantVerify AI', desc, canonical, p.get("feature_image"), "article", extra)
        meta_line = nice_date(p["published_at"]) + (f' · {p["reading_time"]} min read' if p.get("reading_time") else "")
        hero = sf.hero("InstantVerify blog", esc(p["title"]), "").replace("</h1>\n", f'</h1>\n    <div class="post-meta">{meta_line}</div>\n', 1)
        feat = (f'<div class="post-feature"><img src="{esc(p["feature_image"])}" alt="{esc(p.get("feature_image_alt") or "")}"></div>\n'
                if p.get("feature_image") else "")
        body = (hero + '\n\n<main class="doc">\n  <div class="wrap">\n    <a class="back-link" href="/blog/">← All posts</a>\n    '
                + feat + (p.get("html") or "") + '\n    <div class="post-cta"><a class="btn btn-primary" href="/#signup" data-cta="blog_claim_rate">Claim your Charter Practice Rate</a>'
                '<a class="btn btn-ghost" href="/why-us/" data-cta="blog_why_us">Why InstantVerify</a></div>\n    ' + SUBSCRIBE
                + "\n  </div>\n</main>\n" + SUBSCRIBE_JS)
        write(f"blog/{p['slug']}/index.html", sf.frame(head, body, BLOG_CSS))
    # remove pages for posts that were unpublished
    for name in os.listdir("blog"):
        if name not in keep and os.path.isdir(os.path.join("blog", name)):
            shutil.rmtree(os.path.join("blog", name))
    # sitemap: replace the generated block
    sm = open("sitemap.xml").read()
    sm = re.sub(r"\s*<!-- blog:start -->.*?<!-- blog:end -->", "", sm, flags=re.S)
    urls = [f"  <url>\n    <loc>{SITE}/blog/</loc>\n    <lastmod>{posts[0]['published_at'][:10]}</lastmod>\n  </url>"]
    urls += [f"  <url>\n    <loc>{SITE}/blog/{p['slug']}/</loc>\n    <lastmod>{(p.get('updated_at') or p['published_at'])[:10]}</lastmod>\n  </url>" for p in posts]
    sm = sm.replace("</urlset>", "  <!-- blog:start -->\n" + "\n".join(urls) + "\n  <!-- blog:end -->\n</urlset>")
    open("sitemap.xml", "w").write(sm)
    print(f"built blog: {len(posts)} posts")

if __name__ == "__main__":
    build()
