import pathlib, re, sys
ROOT = pathlib.Path("templates")
PAT = re.compile(r'class="(card-header[^"]*)" class="(ch-[^"]+)"')
n = 0
for p in ROOT.rglob("*.html"):
    t = p.read_text("utf-8", "ignore")
    t2, k = PAT.subn(lambda m: f'class="{m.group(1)} {m.group(2)}"', t)
    if k:
        p.write_text(t2, "utf-8")
        n += k
        print(k, p.name)
print("Total:", n)
