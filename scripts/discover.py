"""Discover recent bibliographic candidates. Metadata does not prove archaeological claims.
Full third-party abstracts remain local in .cache, never in public repository.
"""
from __future__ import annotations
import argparse,json,os,re,sys
from datetime import date,timedelta
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from research_core import CONFIG,ROOT,canonical_doi,dump_json,reviewed_keys,is_duplicate,norm,safe_public_url,stable_id,title_score,today_local
SESSION=requests.Session()
SESSION.headers.update({"User-Agent":"ArchaeologyResearchWeekly/1.0 (scholarly bibliography metadata)","Accept":"application/json, text/html;q=0.8"})
SESSION.mount("https://",HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504])))
def get_json(url,params):
    response=SESSION.get(url,params=params,timeout=24)
    response.raise_for_status()
    return response.json()
def publication_date(value):
    for key in ("published-online","published-print","published","issued"):
        dates=(value.get(key) or {}).get("date-parts")
        if dates and dates[0]:
            parts=dates[0]
            return "-".join([str(parts[0])]+[f"{x:02d}" for x in parts[1:]]),len(parts)
    return "",0
def from_crossref(msg):
    title=norm((msg.get("title") or [""])[0]);doi=canonical_doi(msg.get("DOI",""))
    if not title or not doi:return None
    abstract=norm(BeautifulSoup(msg.get("abstract") or "","html.parser").get_text(" ",strip=True))
    published,precision=publication_date(msg)
    authors=", ".join(" ".join(filter(None,[a.get("given",""),a.get("family","")])) for a in msg.get("author",[])[:8])
    journal=norm((msg.get("container-title") or [""])[0])
    kind=msg.get("type","journal-article")
    return dict(id=stable_id(doi,title),doi=doi,title=title,authors=authors or "未提供",journal=journal,published_date=published,url=f"https://doi.org/{doi}",abstract=abstract,provider="Crossref",kind=kind,priority=title_score(title,abstract,journal,kind),published_precision=precision)
def abstract_openalex(inv):
    if not isinstance(inv,dict):return ""
    positions=[]
    for word,ixs in inv.items():
        for i in ixs:
            if isinstance(i,int) and 0<=i<30000:positions.append((i,word))
    return norm(" ".join(word for _,word in sorted(positions)))
def from_openalex(msg):
    title=norm(msg.get("display_name") or msg.get("title") or "")
    doi=canonical_doi(msg.get("doi") or "")
    if not title or not doi:return None
    abstract=abstract_openalex(msg.get("abstract_inverted_index"))
    journal=norm((((msg.get("primary_location") or {}).get("source")) or {}).get("display_name") or "")
    authors=", ".join(a.get("author",{}).get("display_name","") for a in msg.get("authorships",[])[:8])
    kind=msg.get("type","journal-article")
    return dict(id=stable_id(doi,title),doi=doi,title=title,authors=authors or "未提供",journal=journal,published_date=msg.get("publication_date") or "",url=f"https://doi.org/{doi}",abstract=abstract,provider="OpenAlex",kind=kind,priority=title_score(title,abstract,journal,kind),published_precision=3)
def collect_crossref(start,end,warnings):
    collected=[]
    for term in CONFIG["crossref_queries"]:
        try:
            params={"query.bibliographic":term,"filter":f"from-pub-date:{start},until-pub-date:{end}","rows":35,"sort":"published","order":"desc","select":"DOI,title,abstract,author,container-title,published-online,published-print,published,issued,type"}
            data=get_json("https://api.crossref.org/works",params)
            collected.extend(x for item in data.get("message",{}).get("items",[]) if (x:=from_crossref(item)))
        except (requests.RequestException,ValueError,KeyError) as e:
            warnings.append(f"Crossref {term}: {type(e).__name__}: {str(e)[:130]}")
    return collected
def collect_openalex(start,end,warnings):
    key=os.environ.get("OPENALEX_API_KEY","").strip()
    if not key:
        warnings.append("OPENALEX_API_KEY 未配置：跳过 OpenAlex")
        return []
    collected=[]
    for term in CONFIG["openalex_queries"]:
        try:
            params={"search":term,"filter":f"from_publication_date:{start},to_publication_date:{end}","per_page":35,"api_key":key}
            data=get_json("https://api.openalex.org/works",params)
            collected.extend(x for item in data.get("results",[]) if (x:=from_openalex(item)))
        except (requests.RequestException,ValueError,KeyError) as e:
            warnings.append(f"OpenAlex {term}: {type(e).__name__}: {str(e)[:130]}")
    return collected
def collect_official_leads(warnings):
    leads=[]
    for source in CONFIG.get("official_watch_pages",[]):
        try:
            r=SESSION.get(source["url"],timeout=18,headers={"Accept":"text/html"});r.raise_for_status()
            soup=BeautifulSoup(r.text,"html.parser")
            for a in soup.select("a[href]"):
                title=norm(a.get_text(" ",strip=True))
                href=urljoin(source["url"],a.get("href",""))
                host=(urlparse(href).hostname or "").lower()
                if not title or not (host==source["domain"] or host.endswith("."+source["domain"])) or not safe_public_url(href):continue
                if not 8<=len(title)<=90:continue
                issue=bool(re.search(r"《(?:考古|文物|考古与文物|考古学报)》?.{0,18}(?:第.{1,5}期|目录|出刊)",title))
                if not issue and title_score(title,"","")<7:continue
                if any(x in title for x in ("招生","培训","招聘","开班")):continue
                leads.append(dict(id=stable_id("",href),title=title,url=href,provider=source["name"],kind="official_lead",priority=max(title_score(title,"",""),8 if issue else 0),doi="",authors="",journal="",published_date="",abstract=""))
        except requests.RequestException as e:
            warnings.append(f"{source['name']} 页面无法访问：{type(e).__name__}: {str(e)[:80]}")
    return leads
def date_within(value,start,end):
    try:return len(value)>=10 and start<=date.fromisoformat(value[:10])<=end
    except ValueError:return False
def dedupe(items,published_keys,start,end):
    papers={};leads={}
    for item in items:
        if is_duplicate(item,published_keys):continue
        if item.get("kind")!="official_lead" and not date_within(item.get("published_date",""),start,end):continue
        if item["priority"]<(7 if item.get("kind")=="official_lead" else 8):continue
        if item.get("kind")=="official_lead":
            leads[item["url"]]=item;continue
        key=canonical_doi(item.get("doi",""));old=papers.get(key)
        if not old or (bool(item.get("abstract")),len(item.get("abstract","")),item.get("priority",0))>(bool(old.get("abstract")),len(old.get("abstract","")),old.get("priority",0)):
            papers[key]=item
    return sorted(papers.values(),key=lambda x:(-x["priority"],not bool(x["abstract"]),x["title"]))[:CONFIG["top_candidates"]]+sorted(leads.values(),key=lambda x:-x["priority"])[:20]
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",default=today_local())
    p.add_argument("--offline-fixture",help="Synthetic fixture, never for live publication")
    args=p.parse_args()
    end=date.fromisoformat(args.date)
    start=end-timedelta(days=CONFIG["lookback_days"])
    warnings=[]
    if args.offline_fixture:items=json.loads(Path(args.offline_fixture).read_text(encoding="utf-8"))
    else:items=collect_crossref(start,end,warnings)+collect_openalex(start,end,warnings)+collect_official_leads(warnings)
    records=dedupe(items,reviewed_keys(),start,end)
    dump_json(ROOT/".cache/discovery.json",{"date":args.date,"window":{"start":str(start),"end":str(end)},"records":records,"warnings":warnings})
    public=[]
    for r in records:
        x={k:r.get(k) for k in ("id","doi","title","authors","journal","published_date","url","kind","provider","priority")}
        x["abstract_available"]=bool(r.get("abstract"));public.append(x)
    dump_json(ROOT/"content/candidates"/f"{args.date}.json",{"date":args.date,"records":public,"warnings":warnings,"note":"候选元数据不等于学术结论；出版社目录仅供核查，不能自动发表。"})
    print(f"候选 {len(records)} 条；有摘要 {sum(bool(x.get('abstract')) for x in records)} 条；警告 {len(warnings)} 条")
    for w in warnings:print("WARN:",w,file=sys.stderr)
if __name__=="__main__":main()
