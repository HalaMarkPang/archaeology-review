"""Generate static Pages site from checked issues."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse
from jinja2 import Environment, FileSystemLoader, select_autoescape
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site"
ENV = Environment(loader=FileSystemLoader(ROOT / "templates"),autoescape=select_autoescape(["html","xml"]),trim_blocks=True,lstrip_blocks=True)
def load_issues():
    issues=[]
    for path in (ROOT/"content"/"issues").glob("*.json"):
        item=json.loads(path.read_text(encoding="utf-8"))
        assert item["id"]==path.stem,f"Filename/id mismatch: {path}"
        assert all(k in item for k in ("date","period","records","intro"))
        ids=set()
        for r in item["records"]:
            assert r["id"] not in ids;ids.add(r["id"])
            for k in ("title","publication","source_status","core","evidence","analysis","limits","url","period","topic"):
                assert r.get(k),f"Missing {k} in {r['id']}"
            parsed=urlparse(r["url"])
            assert parsed.scheme=="https" and parsed.netloc
            assert r["source_status"] in ("仅核对目录","已核对公开摘要","已核对全文")
            if r["source_status"]=="仅核对目录": assert "待" in r["limits"] or "不" in r["limits"]
        issues.append(item)
    seen={}
    for issue in sorted(issues,key=lambda x:x["date"]):
        for r in issue["records"]:
            normalized="".join(r["title"].split()).replace("（","(").replace("）",")")
            if normalized in seen and not r.get("substantive_update"):
                raise ValueError(f"Repeated work: {r['title']} in {seen[normalized]}")
            seen[normalized]=issue["id"]
    return sorted(issues,key=lambda x:x["date"],reverse=True)
def render(name,path,**ctx):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(ENV.get_template(name).render(**ctx),encoding="utf-8")
def main():
    import shutil
    if OUT.exists():shutil.rmtree(OUT)
    OUT.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/"static",OUT/"static",dirs_exist_ok=True)
    issues=load_issues()
    formal=[x for x in issues if not x.get("is_sample")]
    latest=formal[0] if formal else None
    sf=ROOT/"content"/"status.json"
    status=json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else {"date":"尚未执行","message":"尚无正式刊期","candidates":0,"published":0}
    if latest: render("issue.html",OUT/"index.html",issue=latest,base="",title="本期",location="本期",page="home")
    else:render("landing.html",OUT/"index.html",base="",title="研究周刊",location="首页",page="home",status=status)
    for issue in issues:
        render("issue.html",OUT/"issues"/f"{issue['id']}.html",issue=issue,base="../",title=issue["issue_no"],location="研究精选",page="issue")
    render("archive.html",OUT/"archive"/"index.html",issues=formal,samples=[x for x in issues if x.get("is_sample")],base="../",title="往期归档",location="往期",page="archive")
    (OUT/".nojekyll").touch()
    print(f"Generated {len(formal)} formal issues and {len(issues)-len(formal)} samples")
if __name__=="__main__":main()
