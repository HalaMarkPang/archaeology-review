"""Utilities for archaeological bibliography discovery and audit."""
from __future__ import annotations
import hashlib,json,re,unicodedata
from datetime import datetime
from pathlib import Path
from html import unescape
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/"config/discovery.json").read_text(encoding="utf-8"))
def today_local():return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
def norm(s):return re.sub(r"\s+"," ",unicodedata.normalize("NFKC",unescape(s or ""))).strip()
def slug(s):return re.sub(r"[^a-z0-9\u4e00-\u9fff]","",norm(s).lower())[:140]
def canonical_doi(doi):return (doi or "").replace("https://doi.org/","").replace("http://dx.doi.org/","").lower().strip().lstrip("/")
def stable_id(doi,title):return hashlib.sha256((canonical_doi(doi) or slug(title)).encode("utf-8")).hexdigest()[:16]
def safe_public_url(url):
    try:
        x=urlsplit(url)
        return x.scheme=="https" and bool(x.hostname) and not x.username and not x.password and x.hostname not in ("localhost","127.0.0.1")
    except ValueError:return False
def title_score(title,abstract,journal,kind="journal-article"):
    title,abstract,journal=(norm(x).lower() for x in (title,abstract,journal))
    score=0
    score+=10 if any(x.lower() in title for x in CONFIG["shangzhou_keywords"]) else 0
    score+=3 if any(x.lower() in abstract for x in CONFIG["shangzhou_keywords"]) else 0
    score+=5 if any(x.lower() in title for x in CONFIG["history_keywords"]) else 0
    score+=2 if any(x.lower() in abstract for x in CONFIG["history_keywords"]) else 0
    score+=4 if any(x.lower() in journal for x in CONFIG["priority_journals"]) else 0
    score+=3 if any(x in title for x in ("发掘报告","发掘简报","铭文","墓志","甲骨","inscription","excavation")) else 0
    score-=10 if kind and kind not in ("journal-article","book-chapter","book","article","report","preprint") else 0
    return score
def reviewed_keys():
    keys=set()
    for p in (ROOT/"content/issues").glob("*.json"):
        issue=json.loads(p.read_text(encoding="utf-8"))
        if issue.get("is_sample"):continue
        for r in issue.get("records",[]):
            keys.add("title:"+slug(r.get("title","")))
            if r.get("doi"):keys.add("doi:"+canonical_doi(r["doi"]))
    return keys
def is_duplicate(item,keys):
    doi=canonical_doi(item.get("doi",""))
    return (bool(doi) and "doi:"+doi in keys) or "title:"+slug(item.get("title","")) in keys
def add_seen(item,keys):
    keys.add("title:"+slug(item.get("title","")))
    if item.get("doi"):keys.add("doi:"+canonical_doi(item["doi"]))
def dump_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
