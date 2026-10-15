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
from research_core import CONFIG,ROOT,STANDALONE_GROUP,assess,canonical_doi,dump_json,reviewed_keys,is_duplicate,norm,safe_public_url,slug,stable_id,today_local
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
    scope=assess(title,abstract,journal,kind)
    return dict(id=stable_id(doi,title),doi=doi,title=title,authors=authors or "未提供",journal=journal,published_date=published,url=f"https://doi.org/{doi}",abstract=abstract,provider="Crossref",kind=kind,priority=scope["score"],period_guess=scope["period"],field=scope["field"],in_scope=scope["in_scope"],published_precision=precision)
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
    scope=assess(title,abstract,journal,kind)
    return dict(id=stable_id(doi,title),doi=doi,title=title,authors=authors or "未提供",journal=journal,published_date=msg.get("publication_date") or "",url=f"https://doi.org/{doi}",abstract=abstract,provider="OpenAlex",kind=kind,priority=scope["score"],period_guess=scope["period"],field=scope["field"],in_scope=scope["in_scope"],published_precision=3)
def search_queries():
    queries=[]
    for row in CONFIG["periods"]+CONFIG["fields"]:
        queries.extend(row.get("queries",[]))
    queries.extend(CONFIG.get("umbrella_queries",[]))
    return queries
SELECT="DOI,title,abstract,author,container-title,published-online,published-print,published,issued,type"
def collect_crossref(start,end,warnings):
    collected=[]
    for term in search_queries():
        try:
            params={"query.bibliographic":term,"filter":f"from-pub-date:{start},until-pub-date:{end}","rows":20,"sort":"published","order":"desc","select":SELECT}
            data=get_json("https://api.crossref.org/works",params)
            collected.extend(x for item in data.get("message",{}).get("items",[]) if (x:=from_crossref(item)))
        except (requests.RequestException,ValueError,KeyError) as e:
            warnings.append(f"Crossref {term}: {type(e).__name__}: {str(e)[:130]}")
    return collected
def collect_journal_watch(start,end,warnings):
    """New articles in watched journals, including titles that miss the keyword list."""
    collected=[]
    for name in CONFIG.get("journal_watches",[]):
        try:
            params={"query.container-title":name,"filter":f"from-pub-date:{start},until-pub-date:{end},type:journal-article","rows":15,"select":SELECT}
            data=get_json("https://api.crossref.org/works",params)
            for item in data.get("message",{}).get("items",[]):
                row=from_crossref(item)
                if not row or name.lower() not in row["journal"].lower() or not row.get("in_scope"):continue
                row["watched_journal"]=True
                row["priority"]=max(row["priority"],8)
                collected.append(row)
        except (requests.RequestException,ValueError,KeyError) as e:
            warnings.append(f"期刊 {name}: {type(e).__name__}: {str(e)[:130]}")
    return collected
def collect_openalex(start,end,warnings):
    key=os.environ.get("OPENALEX_API_KEY","").strip()
    if not key:
        warnings.append("OPENALEX_API_KEY 未配置：跳过 OpenAlex")
        return []
    collected=[]
    for term in search_queries():
        try:
            params={"search":term,"filter":f"from_publication_date:{start},to_publication_date:{end}","per_page":35,"api_key":key}
            data=get_json("https://api.openalex.org/works",params)
            collected.extend(x for item in data.get("results",[]) if (x:=from_openalex(item)))
        except (requests.RequestException,ValueError,KeyError) as e:
            warnings.append(f"OpenAlex {term}: {type(e).__name__}: {str(e)[:130]}")
    return collected
def collect_pinned_dois(warnings):
    """Pull works the keyword net missed, when a DOI is already known."""
    collected=[]
    for doi in CONFIG.get("pinned_dois",[]):
        try:
            data=get_json(f"https://api.crossref.org/works/{doi}",{})
            row=from_crossref(data.get("message",{}))
            if row:collected.append(row)
        except (requests.RequestException,ValueError,KeyError) as e:
            warnings.append(f"DOI {doi}: {type(e).__name__}: {str(e)[:130]}")
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
                scope=assess(title,"","")
                if not issue and scope["score"]<8 and scope.get("field")!=STANDALONE_GROUP:continue
                if any(x in title for x in ("招生","培训","招聘","开班")):continue
                leads.append(dict(id=stable_id("",href),title=title,url=href,provider=source["name"],kind="official_lead",priority=max(scope["score"],8 if issue else 0),period_guess=scope["period"],field=scope["field"],doi="",authors="",journal="",published_date="",abstract=""))
        except requests.RequestException as e:
            warnings.append(f"{source['name']} 页面无法访问：{type(e).__name__}: {str(e)[:80]}")
    return leads
def plain_lines(text):
    text=(text or "").replace("\u3000"," ").replace("\xa0"," ")
    return [norm(x) for x in text.splitlines() if norm(x)]
def slice_lines(rows,start,end):
    if start not in rows:return []
    begin=rows.index(start)+1
    stop=begin+rows[begin:].index(end) if end in rows[begin:] else len(rows)
    return rows[begin:stop]
def authors_after(title,toc):
    if title not in toc:return "未提供"
    i=toc.index(title)+1
    while i<len(toc):
        line=toc[i]
        if line.startswith("·") and line.endswith("·"):return "未提供"
        if line.startswith("——") or line.startswith("—"):
            i+=1
            continue
        return line
    return "未提供"
def wenwu_records(text,page_url):
    """Titles and publisher blurbs from a Wenwu issue announcement. No invented finds."""
    if "<" in text and "</" in text:
        soup=BeautifulSoup(text,"html.parser")
        node=soup.select_one(".w-detailcontent") or soup.select_one(".w-detail") or soup
        text=node.get_text("\n",strip=True)
    rows=plain_lines(text)
    joined="\n".join(rows)
    date_m=re.search(r"出版日期[:：](\d{4})年(\d{1,2})月(\d{1,2})日",joined)
    issue_m=re.search(r"《(文物|考古与文物)》(\d{4})年第(\d+)期",joined)
    if not date_m or not issue_m:return []
    published=f"{int(date_m.group(1)):04d}-{int(date_m.group(2)):02d}-{int(date_m.group(3)):02d}"
    journal,year,number=issue_m.group(1),issue_m.group(2),int(issue_m.group(3))
    label=f"《{journal}》{year}年第{number}期"
    toc=slice_lines(rows,"本期目录","精彩摘要")
    blurbs=slice_lines(rows,"精彩摘要","下期要目")
    found=[]
    seen=set()
    i=0
    while i<len(blurbs):
        title=blurbs[i]
        if title in toc and i+1<len(blurbs) and len(blurbs[i+1])>40:
            parts=[]
            i+=1
            while i<len(blurbs) and blurbs[i] not in toc:
                parts.append(blurbs[i]);i+=1
            if title in seen:continue
            seen.add(title)
            abstract=norm("".join(parts))
            scope=assess(title,abstract,journal,"journal_summary")
            found.append(dict(id=stable_id("",title+label),doi="",title=title,authors=authors_after(title,toc),journal=label,published_date=published,url=page_url,abstract=abstract,provider="文物出版社",kind="journal_summary",priority=max(scope["score"],8 if scope["in_scope"] else 0),period_guess=scope["period"],field=scope["field"],in_scope=scope["in_scope"]))
            continue
        i+=1
    i=0
    while i<len(toc):
        line=toc[i]
        if (line.startswith("·") and line.endswith("·")):
            i+=1
            continue
        if line in seen:
            i+=1
            while i<len(toc) and (toc[i].startswith("——") or toc[i].startswith("—")):i+=1
            if i<len(toc) and not (toc[i].startswith("·") and toc[i].endswith("·")):i+=1
            continue
        title=line
        i+=1
        while i<len(toc) and (toc[i].startswith("——") or toc[i].startswith("—")):
            title=norm(title+" "+toc[i].lstrip("—"))
            i+=1
        if i<len(toc) and not (toc[i].startswith("·") and toc[i].endswith("·")):
            author=toc[i]
            i+=1
        else:
            author="未提供"
        if title in seen:continue
        seen.add(title)
        scope=assess(title,"",journal,"journal_toc")
        if not scope["period"] and scope.get("field")!=STANDALONE_GROUP:continue
        found.append(dict(id=stable_id("",title+label),doi="",title=title,authors=author,journal=label,published_date=published,url=page_url,abstract="",provider="文物出版社",kind="journal_toc",priority=8,period_guess=scope["period"],field=scope["field"],in_scope=scope["in_scope"]))
    return found
def collect_wenwu_issues(start,end,warnings):
    collected=[]
    for source in CONFIG.get("chinese_issue_lists",[]):
        try:
            page=SESSION.get(source["url"],timeout=20,headers={"Accept":"text/html"})
            page.raise_for_status();page.encoding=page.apparent_encoding or "utf-8"
            soup=BeautifulSoup(page.text,"html.parser")
            seen=set()
            for a in soup.select("a[href]"):
                title=norm(a.get_text(" ",strip=True))
                href=urljoin(source["url"],a.get("href") or "")
                if href in seen or "出刊" not in title or not re.search(r"《(?:文物|考古与文物)》",title):continue
                if not safe_public_url(href):continue
                seen.add(href)
                article=SESSION.get(href,timeout=20,headers={"Accept":"text/html"})
                article.raise_for_status();article.encoding=article.apparent_encoding or "utf-8"
                for row in wenwu_records(article.text,href):
                    if date_within(row["published_date"],start,end):collected.append(row)
        except requests.RequestException as e:
            warnings.append(f"{source['name']} 页面无法访问：{type(e).__name__}: {str(e)[:80]}")
    return collected
def collect_kaogu_indexes(start,end,warnings):
    """New issue pages. The contents are often an image, so this records the issue, not guessed titles."""
    collected=[]
    for source in CONFIG.get("chinese_toc_indexes",[]):
        try:
            page=SESSION.get(source["url"],timeout=20,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
            page.raise_for_status()
            soup=BeautifulSoup(page.content.decode("utf-8","replace"),"html.parser")
            for a in soup.select("a[href]"):
                title=norm(a.get_text(" ",strip=True))
                dated=re.search(r"(\d{4})年第(\d+)期目录\s+(\d{4}-\d{2}-\d{2})",title)
                if not dated:continue
                published=dated.group(3)
                if not date_within(published,start,end):continue
                href=urljoin(source["url"],a.get("href") or "")
                if not safe_public_url(href):continue
                label=f"《{source['journal']}》{dated.group(1)}年第{int(dated.group(2))}期目录"
                scope=assess(label,"",source["journal"],"official_lead")
                collected.append(dict(id=stable_id("",href),doi="",title=label,authors="",journal=source["journal"],published_date=published,url=href,abstract="",provider="中国考古网",kind="official_lead",priority=max(scope["score"],8),period_guess=scope["period"],field=scope["field"],in_scope=True))
        except requests.RequestException as e:
            warnings.append(f"{source['name']} 目录页无法访问：{type(e).__name__}: {str(e)[:80]}")
    return collected
SKIP_WECHAT=re.compile(r"会议|讲座|展览|招生|书讯|招聘|开班|培训")
def parse_wechat_date(text,today):
    text=norm(text)
    full=re.search(r"(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})",text)
    if full:return date(int(full.group(1)),int(full.group(2)),int(full.group(3)))
    short=re.search(r"(\d{1,2})月(\d{1,2})日",text)
    if short:return date(today.year,int(short.group(1)),int(short.group(2)))
    days=re.search(r"(\d+)\s*天前",text)
    if days:return today-timedelta(days=int(days.group(1)))
    if "昨天" in text:return today-timedelta(days=1)
    if re.search(r"小时前|分钟前",text):return today
    return None
def parse_wechat_html(html,account,today):
    """Titles, account names and dates from one Sogou WeChat result page."""
    soup=BeautifulSoup(html,"html.parser")
    found=[]
    boxes=soup.select("ul.news-list > li") or soup.select("div.txt-box")
    for box in boxes:
        link=box.select_one("h3 a")
        if not link:continue
        title=norm(link.get_text(" ",strip=True))
        if not title:continue
        account_node=box.select_one(".account, .all-time-y2, a[uigs='account_name']")
        shown=norm(account_node.get_text(" ",strip=True) if account_node else "")
        time_node=box.select_one(".s2, span.time, .account + span")
        stamp=norm(time_node.get_text(" ",strip=True) if time_node else box.get_text(" ",strip=True))
        found.append({"title":title,"account":shown or account,"published":parse_wechat_date(stamp,today),"href":link.get("href") or ""})
    next_page=bool(soup.select_one("#sogou_next, a#sogou_next, a.np"))
    return found,next_page
def wechat_coverage(account,pages,start,end,error=""):
    """An account is finished only when its list is exhausted or a page falls before the window."""
    if error:return {"name":account,"status":"未核完","error":error,"articles":[]}
    articles=[];exhausted=False
    for rows,has_next in pages:
        for row in rows:
            published=row.get("published")
            if published and published<start:
                exhausted=True
                continue
            if published and published>end:continue
            if not published:continue
            articles.append(row)
        if exhausted or not has_next:
            exhausted=True
            break
    status="已核完" if exhausted else "未核完"
    return {"name":account,"status":status,"articles":articles}
def collect_wechat_accounts(start,end,warnings,fetch=None,today=None):
    """Page every configured account. A failed or unfinished list is 未核完, never an empty account."""
    today=today or date.today()
    coverage=[]
    leads=[]
    accounts=CONFIG.get("wechat_accounts",[])
    for account in accounts:
        name=account["name"];query=account.get("query") or name
        pages=[];error=""
        try:
            for page in range(1,9):
                html=fetch(query,page) if fetch else fetch_wechat_page(query,page,start,end)
                rows,has_next=parse_wechat_html(html,name,today)
                own=[row for row in rows if not row["account"] or name in row["account"] or row["account"] in name]
                pages.append((own,has_next))
                if any(row.get("published") and row["published"]<start for row in own) or not has_next:break
            report=wechat_coverage(name,pages,start,end)
        except (requests.RequestException,ValueError,OSError) as e:
            report=wechat_coverage(name,[],start,end,error=f"{type(e).__name__}: {str(e)[:80]}")
        entry={"name":name,"status":report["status"],"articles":[{"title":row["title"],"published_date":row["published"].isoformat()} for row in report["articles"]]}
        if report.get("error"):entry["error"]=report["error"]
        coverage.append(entry)
        if report["status"]!="已核完":
            warnings.append(f"公众号「{name}」未核完"+(f"：{report['error']}" if report.get("error") else "：列表未翻完"))
        for row in report["articles"]:
            scope=assess(row["title"],"",name,"wechat_lead")
            if SKIP_WECHAT.search(row["title"]) and scope.get("field")!=STANDALONE_GROUP:continue
            if not scope["in_scope"] and not scope["period"]:continue
            href=row["href"] if safe_public_url(row["href"]) else ""
            leads.append(dict(id=stable_id("",name+row["title"]),doi="",title=row["title"],authors=name,journal=name,published_date=row["published"].isoformat(),url=href,abstract="",provider=name,kind="wechat_lead",priority=max(scope["score"],8),period_guess=scope["period"],field=scope["field"],in_scope=scope["in_scope"]))
    return leads,coverage
def fetch_wechat_page(query,page,start,end):
    response=SESSION.get("https://weixin.sogou.com/weixin",params={"type":"2","query":query,"ie":"utf8","page":page,"tsn":"5","ft":start.isoformat(),"et":end.isoformat()},timeout=20,headers={"Accept":"text/html","User-Agent":"Mozilla/5.0"})
    response.raise_for_status()
    if "antispider" in response.url or "请输入验证码" in response.text:raise requests.RequestException("搜狗微信拦截")
    return response.text
def date_within(value,start,end):
    try:return len(value)>=10 and start<=date.fromisoformat(value[:10])<=end
    except ValueError:return False
def dedupe(items,published_keys,start,end):
    papers={};leads={}
    for item in items:
        if is_duplicate(item,published_keys):continue
        if item.get("kind")!="official_lead" and not date_within(item.get("published_date",""),start,end):continue
        if item["priority"]<(7 if item.get("kind")=="official_lead" else 8):continue
        if item.get("kind") in ("official_lead","wechat_lead"):
            leads[item.get("url") or item["id"]]=item;continue
        key=canonical_doi(item.get("doi","")) or "title:"+slug(item.get("title",""))
        old=papers.get(key)
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
    else:
        wechat_leads,wechat_checked=collect_wechat_accounts(start,end,warnings)
        items=collect_crossref(start,end,warnings)+collect_journal_watch(start,end,warnings)+collect_openalex(start,end,warnings)+collect_pinned_dois(warnings)+collect_wenwu_issues(start,end,warnings)+collect_kaogu_indexes(start,end,warnings)+collect_official_leads(warnings)+wechat_leads
    if args.offline_fixture:wechat_checked=[]
    records=dedupe(items,reviewed_keys(),start,end)
    dump_json(ROOT/".cache/discovery.json",{"date":args.date,"window":{"start":str(start),"end":str(end)},"records":records,"warnings":warnings,"wechat_accounts":wechat_checked})
    public=[]
    for r in records:
        x={k:r.get(k) for k in ("id","doi","title","authors","journal","published_date","url","kind","provider","priority","period_guess","field")}
        x["watched_journal"]=bool(r.get("watched_journal"))
        x["abstract_available"]=bool(r.get("abstract"));public.append(x)
    dump_json(ROOT/"content/candidates"/f"{args.date}.json",{"date":args.date,"records":public,"warnings":warnings,"wechat_accounts":wechat_checked,"note":"候选记录为题录，尚非已发表结论。出版社目录供核查。公众号未核完，表示该号检索尚未完成。"})
    print(f"候选 {len(records)} 条；有摘要 {sum(bool(x.get('abstract')) for x in records)} 条；警告 {len(warnings)} 条")
    for w in warnings:print("WARN:",w,file=sys.stderr)
if __name__=="__main__":main()
