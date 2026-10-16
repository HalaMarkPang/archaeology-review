"""Generate static Pages site from checked issues."""
from __future__ import annotations
import html,json,re
from pathlib import Path
from urllib.parse import urlparse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
sys_path = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(sys_path / "scripts"))
from research_core import CONFIG, STANDALONE_GROUP, canonical_doi, slug
from editorial import validate_issue
ROOT = sys_path
OUT = ROOT / "site"
def emphasize(text):
    safe=html.escape(text or "")
    safe=re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe=re.sub(r"__(.+?)__", r'<span class="point">\1</span>', safe)
    return Markup(safe)
ENV = Environment(loader=FileSystemLoader(ROOT / "templates"),autoescape=select_autoescape(["html","xml"]),trim_blocks=True,lstrip_blocks=True)
ENV.filters["emphasize"]=emphasize
def display_span(period):
    parts=re.split(r"\s*[—–]\s*|\s+-\s+", period or "")
    def zh(token):
        matched=re.match(r"(\d{4})-(\d{2})-(\d{2})", token.strip())
        if not matched:return ""
        return f"{int(matched.group(2))}月{int(matched.group(3))}日"
    if len(parts)>=2:
        start,end=zh(parts[0]),zh(parts[1])
        if start and end:
            if parts[0].strip()[:4]!=parts[1].strip()[:4]:return f"{parts[0].strip()[:4]}年{start}—{parts[1].strip()[:4]}年{end}"
            return f"{start}—{end}"
    return period or ""
def prepare(issue):
    item=dict(issue)
    item["display_span"]=display_span(item.get("period") or "")
    groups=[]
    for genre in CONFIG["genres"]:
        records=[r for r in issue["records"] if r["kind"]==genre and r["period"]!=STANDALONE_GROUP]
        if records:groups.append({"label":genre,"records":records})
    theory=[r for r in issue["records"] if r["period"]==STANDALONE_GROUP]
    if theory:groups.append({"label":STANDALONE_GROUP,"records":theory})
    item["groups"]=groups
    return item
EDITION={
    "genres":CONFIG.get("genres") or [],
    "periods":[row["label"] for row in CONFIG.get("periods") or []],
    "theory":STANDALONE_GROUP,
}
def load_issues():
    issues=[]
    for path in (ROOT/"content"/"issues").glob("*.json"):
        item=json.loads(path.read_text(encoding="utf-8"))
        if item["id"]!=path.stem:raise ValueError(f"Filename/id mismatch: {path}")
        validate_issue(item,root=ROOT)
        issues.append(item)
    seen_titles={};seen_dois={}
    for issue in sorted(issues,key=lambda x:x["date"]):
        if issue.get("is_sample"):continue
        for r in issue["records"]:
            title=slug(r["title"]);doi=canonical_doi(r.get("doi",""))
            if (title in seen_titles or (doi and doi in seen_dois)) and not r.get("substantive_update"):
                raise ValueError(f"Repeated work: {r['title']}")
            seen_titles[title]=issue["id"]
            if doi:seen_dois[doi]=issue["id"]
    return sorted(issues,key=lambda x:x["date"],reverse=True)
def render(name,path,**ctx):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(ENV.get_template(name).render(**ctx),encoding="utf-8")
def main():
    import shutil
    issues=[prepare(item) for item in load_issues()]
    if OUT.exists():shutil.rmtree(OUT)
    OUT.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/"static",OUT/"static",dirs_exist_ok=True)
    formal=[x for x in issues if not x.get("is_sample")]
    latest=formal[0] if formal else None
    sf=ROOT/"content"/"status.json"
    status=json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else {"date":"尚未执行","message":"尚无正式刊期","candidates":0,"published":0}
    if latest: render("issue.html",OUT/"index.html",issue=latest,edition=EDITION,base="",title="本期",location="本期",page="home")
    else:render("landing.html",OUT/"index.html",base="",title="考古-周刊",location="首页",page="home",status=status)
    for issue in issues:
        render("issue.html",OUT/"issues"/f"{issue['id']}.html",issue=issue,edition=EDITION,base="../",title=issue["issue_no"],location="研究精选",page="issue")
    render("archive.html",OUT/"archive"/"index.html",issues=formal,samples=[x for x in issues if x.get("is_sample")],base="../",title="往期归档",location="往期",page="archive")
    index=[]
    for issue in formal:
        for r in issue["records"]:
            index.append({"title":r.get("headline") or r["title"],"original_title":r["title"],"citation":r["authors"]+" · "+r["publication"],"body":re.sub(r"\*\*|__","",r["core"]),"url":f"issues/{issue['id']}.html#{r['id']}"})
    (OUT/"search-index.json").write_text(json.dumps(index,ensure_ascii=False),encoding="utf-8")
    (OUT/".nojekyll").touch()
    print(f"Generated {len(formal)} formal issues and {len(issues)-len(formal)} samples")
if __name__=="__main__":main()
