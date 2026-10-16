"""Utilities for archaeological bibliography discovery and audit."""
from __future__ import annotations
import hashlib,json,re,unicodedata,ipaddress
from datetime import datetime
from pathlib import Path
from html import unescape
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/"config/discovery.json").read_text(encoding="utf-8"))
STANDALONE_GROUP=CONFIG.get("standalone_group") or "考古学理论"
def local_zone():return ZoneInfo(CONFIG.get("schedule",{}).get("timezone") or "Asia/Shanghai")
def today_local():return datetime.now(local_zone()).date().isoformat()
def norm(s):return re.sub(r"\s+"," ",unicodedata.normalize("NFKC",unescape(s or ""))).strip()
def slug(s):return re.sub(r"[^a-z0-9\u4e00-\u9fff]","",norm(s).lower())[:140]
def canonical_doi(doi):return (doi or "").replace("https://doi.org/","").replace("http://dx.doi.org/","").lower().strip().lstrip("/")
def stable_id(doi,title):return hashlib.sha256((canonical_doi(doi) or slug(title)).encode("utf-8")).hexdigest()[:16]
def safe_public_url(url):
    try:
        x=urlsplit(url)
        if x.scheme not in ("https","http") or not x.hostname or x.username or x.password or x.hostname.lower()=="localhost":return False
        try:return ipaddress.ip_address(x.hostname).is_global
        except ValueError:return "." in x.hostname
    except ValueError:return False
ALLOWED_KINDS=("journal-article","book-chapter","book","article","report","preprint","official_lead","journal_summary","journal_toc","wechat_lead","")
GENERIC_PERIOD_TERMS={"paleolithic","palaeolithic","neolithic"}
def text_blob(*parts):
    return norm(" ".join(p or "" for p in parts)).lower().replace("-"," ").replace("–"," ").replace("—"," ")
def hit_terms(blob,terms):
    found=[]
    for term in terms:
        needle=term.lower().replace("-"," ")
        if needle and needle in blob:found.append(term)
    return found
def best_label(rows,title_blob,blob):
    found=[]
    for row in rows:
        title_hits=hit_terms(title_blob,row["terms"])
        any_hits=title_hits or hit_terms(blob,row["terms"])
        if not any_hits:continue
        term=max(any_hits,key=len)
        found.append((1 if title_hits else 0,len(term),row["label"],term))
    if not found:return "",""
    found.sort(key=lambda item:(item[0],item[1]),reverse=True)
    return found[0][2],found[0][3]
def matched_journal(journal):
    blob=text_blob(journal)
    names=sorted(CONFIG.get("priority_journals",[]),key=len,reverse=True)
    for name in names:
        if name.lower().replace("-"," ")==blob or (name in CONFIG.get("core_journals",[]) and re.fullmatch(r"《?"+re.escape(name)+r"》?(?:\d{4}年第\d+期)?",blob)):return name
    return ""
def assess(title,abstract="",journal="",kind="journal-article"):
    """Return period, field, score, and whether the item is inside the editorial scope."""
    blob=text_blob(title,abstract,journal)
    title_blob=text_blob(title)
    period,period_term=best_label(CONFIG["periods"],title_blob,blob)
    field,field_term=best_label(CONFIG["fields"],title_blob,blob)
    # Applying spatial methods to one dataset does not make it a theory paper.
    theory_terms=CONFIG.get("theory_terms",[])
    if field==STANDALONE_GROUP and not hit_terms(title_blob,theory_terms) and not hit_terms(blob,["考古学理论","archaeological theory"]):
        field,field_term="",""
    qing=bool(hit_terms(blob,CONFIG.get("exclude_qing",[])))
    song_yuan_ming=bool(hit_terms(blob,next(row["terms"] for row in CONFIG["periods"] if row["label"]=="宋元明")))
    china=bool(hit_terms(blob,CONFIG.get("china_anchors",[]))) or bool(re.search(r"[\u4e00-\u9fff]",field_term))
    journal_name=matched_journal(journal)
    core=journal_name in CONFIG.get("core_journals",[])
    if period_term.lower().replace("-"," ") in GENERIC_PERIOD_TERMS and not (china or core):
        period,period_term="",""
    if kind and kind not in ALLOWED_KINDS:
        return {"period":"","field":"","score":0,"in_scope":False,"journal":journal_name}
    if qing and not song_yuan_ming:
        return {"period":"","field":"","score":0,"in_scope":False,"journal":journal_name}
    theory=field==STANDALONE_GROUP
    in_scope=bool(period) or bool(field and (china or core)) or bool(core and not qing) or theory
    score=0
    if period:score+=8
    if field:score+=4
    if journal_name:score+=4
    if not in_scope:score=0
    return {"period":period,"field":field,"score":score,"in_scope":in_scope,"journal":journal_name,"term":period_term or field_term}
def title_score(title,abstract,journal,kind="journal-article"):
    return assess(title,abstract,journal,kind)["score"]
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
