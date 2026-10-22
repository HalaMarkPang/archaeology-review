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
from publication_window import weekly_window, publication_membership
SESSION=requests.Session()
SESSION.headers.update({"User-Agent":"ArchaeologyResearchWeekly/1.0 (scholarly bibliography metadata)","Accept":"application/json, text/html;q=0.8"})
COVERAGE=[]
SESSION.mount("http://",HTTPAdapter(max_retries=Retry(total=2,backoff_factor=1,status_forcelist=[429,500,502,503,504])))
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
    title=norm(BeautifulSoup((msg.get("title") or [""])[0],"html.parser").get_text(" ",strip=True));doi=canonical_doi(msg.get("DOI",""))
    if not title or not doi:return None
    abstract=norm(BeautifulSoup(msg.get("abstract") or "","html.parser").get_text(" ",strip=True))
    published,precision=publication_date(msg)
    authors=", ".join(" ".join(filter(None,[a.get("given",""),a.get("family","")])) for a in msg.get("author",[]))
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
    authors=", ".join(a.get("author",{}).get("display_name","") for a in msg.get("authorships",[]))
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
def error_message(exc):
    return re.sub(r"(?i)(api_key|token|authorization)(=|%3D|:)[^&\s]+",r"\1=[redacted]",str(exc))[:160]

def api_pages(url,params,provider,label,warnings):
    """Consume a cursor, explicitly recording any budget/response boundary."""
    cursor="*";visited=set();count=0;pages=0;state="partial";reason="page_budget"
    size=int(CONFIG.get("api_page_size",100))
    try:
        for page in range(int(CONFIG.get("api_max_pages",5))):
            if cursor in visited:reason="repeated_cursor";break
            visited.add(cursor);args=dict(params,cursor=cursor)
            args["rows" if provider=="Crossref" else "per_page"]=size
            data=get_json(url,args);pages+=1
            block=data.get("message",{}) if provider=="Crossref" else data
            key="items" if provider=="Crossref" else "results"
            if key not in block or not isinstance(block[key],list):raise ValueError("API response schema changed")
            rows=block[key];count+=len(rows)
            yield from rows
            next_cursor=block.get("next-cursor") if provider=="Crossref" else block.get("meta",{}).get("next_cursor")
            if len(rows)<size or not next_cursor:
                state="complete";reason="response_exhausted";break
            cursor=next_cursor
    except (requests.RequestException,ValueError,KeyError) as exc:
        state="failed" if not pages else "partial";reason=error_message(exc)
    if state!="complete":warnings.append(f"{provider} {label}: {state} ({reason})")
    COVERAGE.append({"source":provider,"query":label,"pages":pages,"retrieved":count,"status":state,"reason":reason})

def collect_crossref(start,end,warnings):
    collected=[]
    for term in search_queries():
        params={"query.bibliographic":term,"filter":f"from-pub-date:{start},until-pub-date:{end}","sort":"published","order":"desc","select":SELECT}
        collected.extend(x for item in api_pages("https://api.crossref.org/works",params,"Crossref",term,warnings) if (x:=from_crossref(item)))
    return collected

def collect_journal_watch(start,end,warnings):
    collected=[]
    for name in CONFIG.get("journal_watches",[]):
        params={"filter":f"from-pub-date:{start},until-pub-date:{end},type:journal-article","select":SELECT}
        issn=CONFIG.get("journal_identifiers",{}).get(name)
        url=f"https://api.crossref.org/journals/{issn}/works" if issn else "https://api.crossref.org/works"
        if not issn:params["query.container-title"]=name
        for item in api_pages(url,params,"Crossref",name,warnings):
            row=from_crossref(item)
            if not row or norm(row["journal"]).casefold()!=norm(name).casefold():continue
            row["watched_journal"]=True;row["priority"]=max(row["priority"],8);collected.append(row)
    return collected

def collect_openalex(start,end,warnings):
    key=os.environ.get("OPENALEX_API_KEY","").strip()
    if not key:
        warnings.append("OPENALEX_API_KEY未配置，未检索OpenAlex")
        COVERAGE.append({"source":"OpenAlex","status":"skipped","reason":"missing_key"});return []
    collected=[]
    for term in search_queries():
        params={"search":term,"filter":f"from_publication_date:{start},to_publication_date:{end}","api_key":key}
        collected.extend(x for item in api_pages("https://api.openalex.org/works",params,"OpenAlex",term,warnings) if (x:=from_openalex(item)))
    return collected

def web_pages(source,warnings):
    """Follow only an explicit same-site next link. No guessed pagination URLs."""
    url=source["url"];seen=set();count=0;state="partial";reason="page_budget"
    try:
        for _ in range(int(CONFIG.get("web_max_pages",5))):
            if url in seen:reason="repeated_page";break
            seen.add(url)
            r=SESSION.get(url,timeout=20,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"});r.raise_for_status()
            r.encoding=r.apparent_encoding or "utf-8"
            soup=BeautifulSoup(r.text,"html.parser");count+=1
            yield soup,url
            next_link=soup.select_one('a[rel="next"]')
            if next_link is None:
                next_link=next((a for a in soup.select("a[href]") if norm(a.get_text()) in ("下一页","下页","Next",">")),None)
            if next_link is None:
                # Absence of recognised pagination cannot prove that a site is exhausted.
                reason="no_verified_next_link";break
            candidate=urljoin(url,next_link.get("href") or "")
            if not safe_public_url(candidate) or urlparse(candidate).hostname!=urlparse(source["url"]).hostname:reason="unverified_next_link";break
            url=candidate
    except requests.RequestException as exc:
        state="failed" if not count else "partial";reason=error_message(exc)
    COVERAGE.append({"source":source["name"],"url":source["url"],"pages":count,"status":state,"reason":reason})
    if state!="complete":warnings.append(f"{source['name']}：覆盖尚未核完（{reason}）")

def collect_pinned_dois(warnings):
    """Pull works the keyword net missed, when a DOI is already known."""
    collected=[]
    for doi in CONFIG.get("pinned_dois",[]):
        try:
            data=get_json(f"https://api.crossref.org/works/{doi}",{})
            row=from_crossref(data.get("message",{}))
            if row:collected.append(row)
        except (requests.RequestException,ValueError,KeyError) as e:
            warnings.append(f"DOI {doi}: {type(e).__name__}: {error_message(e)}")
    return collected
def collect_official_leads(warnings):
    leads=[]
    for source in CONFIG.get("official_watch_pages",[]):
        for soup,page_url in web_pages(source,warnings):
            for a in soup.select("a[href]"):
                title=norm(a.get_text(" ",strip=True));href=urljoin(page_url,a.get("href", ""))
                host=(urlparse(href).hostname or "").lower()
                if not title or not (host==source["domain"] or host.endswith("."+source["domain"])) or not safe_public_url(href):continue
                if not 8<=len(title)<=120 or any(x in title for x in ("招生","培训","招聘","开班")):continue
                scope=assess(title,"", "")
                leads.append(dict(id=stable_id("",href),title=title,url=href,provider=source["name"],kind="official_lead",priority=scope["score"],period_guess=scope["period"],field=scope["field"],doi="",authors="",journal="",published_date="",abstract=""))
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
        found.append(dict(id=stable_id("",title+label),doi="",title=title,authors=author,journal=label,published_date=published,url=page_url,abstract="",provider="文物出版社",kind="journal_toc",priority=8,period_guess=scope["period"],field=scope["field"],in_scope=scope["in_scope"]))
    return found
def collect_wenwu_issues(start,end,warnings):
    collected=[];seen=set()
    for source in CONFIG.get("chinese_issue_lists",[]):
        for soup,page_url in web_pages(source,warnings):
            for a in soup.select("a[href]"):
                title=norm(a.get_text(" ",strip=True));href=urljoin(page_url,a.get("href") or "")
                if href in seen or "出刊" not in title or not re.search(r"《(?:文物|考古与文物)》",title):continue
                if not safe_public_url(href) or urlparse(href).hostname!=urlparse(source["url"]).hostname:continue
                seen.add(href)
                try:
                    article=SESSION.get(href,timeout=20,headers={"Accept":"text/html"});article.raise_for_status();article.encoding=article.apparent_encoding or "utf-8"
                    collected.extend(row for row in wenwu_records(article.text,href) if date_within(row["published_date"],start,end))
                except requests.RequestException as exc:warnings.append(f"出刊页{href}: {error_message(exc)}")
    return collected

def collect_kaogu_indexes(start,end,warnings):
    collected=[]
    for source in CONFIG.get("chinese_toc_indexes",[]):
        for soup,page_url in web_pages(source,warnings):
            for a in soup.select("a[href]"):
                title=norm(a.get_text(" ",strip=True));dated=re.search(r"(\d{4})年第(\d+)期目录\s+(\d{4}-\d{2}-\d{2})",title)
                if not dated or not date_within(dated.group(3),start,end):continue
                href=urljoin(page_url,a.get("href") or "")
                if not safe_public_url(href):continue
                label=f"《{source['journal']}》{dated.group(1)}年第{int(dated.group(2))}期目录"
                collected.append(dict(id=stable_id("",href),doi="",title=label,authors="",journal=source["journal"],published_date=dated.group(3),url=href,abstract="",provider="中国考古网",kind="official_lead",priority=8,period_guess="",field="",in_scope=True))
    return collected
SKIP_WECHAT=re.compile(r"会议|讲座|展览|招生|书讯|招聘|开班|培训")
def parse_wechat_date(text,today):
    text=norm(text)
    full=re.search(r"(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})",text)
    if full:return date(int(full.group(1)),int(full.group(2)),int(full.group(3)))
    short=re.search(r"(\d{1,2})月(\d{1,2})日",text)
    if short:
        parsed=date(today.year,int(short.group(1)),int(short.group(2)))
        return parsed.replace(year=today.year-1) if parsed>today else parsed
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
        found.append({"title":title,"account":shown,"published":parse_wechat_date(stamp,today),"href":link.get("href") or ""})
    next_page=bool(soup.select_one("#sogou_next, a#sogou_next, a.np"))
    return found,next_page
def wechat_coverage(account,pages,start,end,error=""):
    articles=[];seen=set()
    for rows,has_next in pages:
        for row in rows:
            stamp=row.get("published")
            if row.get("account")!=account or not stamp or not start<=stamp<=end:continue
            key=(row["title"],stamp)
            if key not in seen:articles.append(row);seen.add(key)
    return {"name":account,"status":"未核完","method":"搜狗搜索补充","reason":"搜索结果不能证明账号文章列表完整","articles":articles,**({"error":error} if error else {})}

def collect_wechat_accounts(start,end,warnings,fetch=None,today=None):
    today=today or date.fromisoformat(today_local());coverage=[];leads=[]
    for account in CONFIG.get("wechat_accounts",[]):
        name=account["name"];query=account.get("query") or name;pages=[];error=""
        try:
            for page in range(1,int(CONFIG.get("wechat_max_pages",8))+1):
                html=fetch(query,page) if fetch else fetch_wechat_page(query,page,start,end)
                rows,has_next=parse_wechat_html(html,name,today)
                if not rows:raise ValueError("页面未识别到有效搜索结果")
                pages.append(([row for row in rows if row["account"]==name],has_next))
                if not has_next:break
        except (requests.RequestException,ValueError,OSError) as exc:error=f"{type(exc).__name__}: {error_message(exc)}"
        report=wechat_coverage(name,pages,start,end,error=error)
        entry={k:v for k,v in report.items() if k!="articles"}
        entry["pages"]=len(pages);entry["articles"]=[{"title":x["title"],"published_date":x["published"].isoformat()} for x in report["articles"]]
        coverage.append(entry);warnings.append(f"公众号「{name}」仅作搜索补充，尚未核完账号列表"+(f"：{error}" if error else ""))
        for row in report["articles"]:
            scope=assess(row["title"],"",name,"wechat_lead")
            if SKIP_WECHAT.search(row["title"]) and scope.get("field")!=STANDALONE_GROUP:continue
            href=urljoin("https://weixin.sogou.com/",row["href"])
            leads.append(dict(id=stable_id("",name+row["title"]),doi="",title=row["title"],authors=name,journal=name,published_date=row["published"].isoformat(),url=href if safe_public_url(href) else "",abstract="",provider=name,kind="wechat_lead",priority=scope["score"],period_guess=scope["period"],field=scope["field"],in_scope=scope["in_scope"]))
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
    papers=[];leads={};by_title={};by_doi={}
    for item in items:
        if item.get("kind") in ("official_lead","wechat_lead"):
            if item.get("kind")=="official_lead" or date_within(item.get("published_date",""),start,end):leads[item.get("url") or item["id"]]=item
            continue
        # Keep unclassified, lower-scoring and previously published candidates for the audit.
        value=item.get("published_date","")
        if not date_within(value,start,end) and not (len(value)==7 and start.isoformat()[:7]<=value<=end.isoformat()[:7]) and not (len(value)==4 and str(start.year)<=value<=str(end.year)):continue
        doi=canonical_doi(item.get("doi", ""));title=slug(item.get("title", ""))
        old=by_doi.get(doi) if doi else None
        old=old or by_title.get(title)
        if old:
            if item.get("abstract") and not old.get("abstract"):
                identity={k:old.get(k) for k in ("id","doi","url") if old.get(k)}
                old.update(item)
                if identity.get("doi"):old.update(identity)
            elif doi and not old.get("doi"):old["doi"]=doi
        else:old=dict(item);papers.append(old)
        by_title[title]=old
        if doi:by_doi[doi]=old
    return sorted(papers,key=lambda x:(-x.get("priority",0),not bool(x.get("abstract")),x["title"]))+sorted(leads.values(),key=lambda x:-x.get("priority",0))
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",help="原定周五的日期；补跑时保持原刊期窗口")
    p.add_argument("--show-window",action="store_true",help="仅显示本期窗口，不检索或写文件")
    p.add_argument("--offline-fixture",help="Synthetic fixture, never for live publication")
    args=p.parse_args()
    window=weekly_window(args.date)
    if args.show_window:
        print(json.dumps(window,ensure_ascii=False,indent=2));return
    issue_date=window["end"]
    start=date.fromisoformat(window["start"]);end=date.fromisoformat(window["end"])
    warnings=[];COVERAGE.clear()
    if args.offline_fixture:items=json.loads(Path(args.offline_fixture).read_text(encoding="utf-8"))
    else:
        wechat_leads,wechat_checked=collect_wechat_accounts(start,end,warnings)
        items=collect_crossref(start,end,warnings)+collect_journal_watch(start,end,warnings)+collect_openalex(start,end,warnings)+collect_pinned_dois(warnings)+collect_wenwu_issues(start,end,warnings)+collect_kaogu_indexes(start,end,warnings)+collect_official_leads(warnings)+wechat_leads
    if args.offline_fixture:wechat_checked=[]
    records=dedupe(items,reviewed_keys(),start,end)
    for record in records:record["window_status"]=publication_membership(record,window)
    dump_json(ROOT/".cache/discovery.json",{"date":issue_date,"window":window,"records":records,"warnings":warnings,"wechat_accounts":wechat_checked,"coverage":COVERAGE,"synthetic":bool(args.offline_fixture)})
    public=[]
    for r in records:
        x={k:r.get(k) for k in ("id","doi","title","authors","journal","published_date","published_at","published_at_source","window_status","url","kind","provider","priority","period_guess","field")}
        x["watched_journal"]=bool(r.get("watched_journal"))
        x["abstract_available"]=bool(r.get("abstract"));public.append(x)
    dump_json(ROOT/"content/candidates"/f"{issue_date}.json",{"date":issue_date,"window":window,"records":public,"warnings":warnings,"wechat_accounts":wechat_checked,"coverage":COVERAGE,"synthetic":bool(args.offline_fixture),"note":"候选记录为题录，尚非已发表结论。起止日无发表时刻者待核对。出版社目录供核查。公众号未核完，表示该号检索尚未完成。"})
    print(f"候选 {len(records)} 条；有摘要 {sum(bool(x.get('abstract')) for x in records)} 条；警告 {len(warnings)} 条")
    for w in warnings:print("WARN:",w,file=sys.stderr)
if __name__=="__main__":main()
