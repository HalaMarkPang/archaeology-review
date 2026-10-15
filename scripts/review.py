"""Publish verbatim abstract excerpts. No paid model, no paraphrase.
Quoted lines must be contiguous substrings of the source abstract.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re
from pathlib import Path
from research_core import CONFIG,ROOT,STANDALONE_GROUP,assess,canonical_doi,dump_json,norm,reviewed_keys,is_duplicate,add_seen,today_local,safe_public_url,slug
MIN_ABSTRACT_CHARS=160
MAX_ATTEMPTS=20
def anchored(quote,abstract):
    q=norm(quote);s=norm(abstract)
    return 12<=len(q)<=240 and q in s
def validate_extract(output,item):
    if not isinstance(output,dict) or output.get("relevant") is not True:
        return False,str(output.get("reason","摘要证据不足")) if isinstance(output,dict) else "无效摘录"
    for key in ("core","analysis","newness","period","topic","kind","limits"):
        if not isinstance(output.get(key),str) or len(output[key].strip())<2:return False,f"缺少{key}"
    if not 35<=len(output["core"])<=350:return False,"核心发现长度不符"
    if not anchored(output.get("core_quote",""),item["abstract"]):return False,"核心发现缺少逐字摘要依据"
    es=output.get("evidence",[])
    if not isinstance(es,list) or not 2<=len(es)<=3:return False,"必须有2—3条关键证据"
    positions=[]
    for e in es:
        if not isinstance(e,dict) or not isinstance(e.get("claim"),str) or len(norm(e["claim"]))<10 or not anchored(e.get("quote",""),item["abstract"]):
            return False,"证据语句与摘要无法逐字匹配"
        positions.append(norm(item["abstract"]).find(norm(e["quote"])))
    if len(set(positions))<2:return False,"证据未覆盖两个独立摘要位置"
    if not item.get("doi") or not safe_public_url(item.get("url","")):return False,"缺少规范 DOI/原始链接"
    return True,""
def clip_quote(text):
    text=norm(text)
    return text if len(text)<=220 else text[:220]
def sentences(abstract):
    parts=re.split(r"(?<=[。！？.!?])\s*",norm(abstract))
    return [p.strip() for p in parts if len(norm(p))>=48]
def publication_track(scope):
    """Theory is its own group and does not take a dynasty label."""
    if scope.get("field")==STANDALONE_GROUP:return STANDALONE_GROUP
    return scope.get("period") or ""
def classify(item):
    scope=assess(item.get("title",""),item.get("abstract",""),item.get("journal",""),item.get("kind",""))
    period=publication_track(scope) or "其他"
    topic=scope["field"] or period
    return period,topic
def load_brief(doi,title=""):
    names=[]
    if doi:names.append(canonical_doi(doi).replace("/", "_"))
    if title:names.append(slug(title))
    for name in names:
        path=ROOT/"content"/"briefs"/f"{name}.md"
        if not path.exists():continue
        text=path.read_text(encoding="utf-8").strip()
        parts=re.split(r"\n\s*\n",text,maxsplit=1)
        if len(parts)==2 and 4<=len(parts[0].strip())<=40:
            return parts[0].strip(),parts[1].strip()
        return "",text
    return "",""
def chinese_body(item):
    headline,body=load_brief(item.get("doi",""),item.get("title",""))
    if body:return headline,body
    zh=[s for s in sentences(item.get("abstract","")) if re.search(r"[\u4e00-\u9fff]",s)]
    if len("".join(zh))<35:return "",""
    text="\n\n".join(zh if item.get("kind")=="journal_summary" else zh[:2])
    if item.get("kind")=="journal_summary":return "",text[:900]
    return text.split("。")[0][:40],text
def genre(title):
    title=title or ""
    if "调查" in title and ("简报" in title or title.endswith("调查")):return "调查简报"
    if "简报" in title:return "发掘简报"
    if "发掘报告" in title:return "发掘报告"
    if "博物馆" in title and "藏" in title:return "馆藏研究"
    if any(x in title for x in ("墓志","铭文","甲骨","简牍","金文","碑刻")):return "出土文献"
    return "研究论文"
def excerpt_extract(item):
    found=sentences(item.get("abstract",""))
    if len(found)<2:return {"relevant":False,"reason":"摘要不足两条独立原句"}
    q1,q2=clip_quote(found[0]),clip_quote(found[-1])
    if norm(q1)==norm(q2):return {"relevant":False,"reason":"摘要原句位置重复"}
    period,topic=classify(item)
    title=item.get("title","")
    kind=genre(title)
    return {"relevant":True,"core":q1,"core_quote":q1,
        "evidence":[{"claim":q1,"quote":q1},{"claim":q2,"quote":q2}],
        "analysis":q2,"newness":"新发表研究","period":period,"topic":topic,"kind":kind,"limits":"未核对全文"}
def to_record(item,x):
    doi=item["doi"];journal=item["journal"] or "出版信息待补充"
    publication=f"{journal}，{item['published_date']}"+(f"，DOI：{doi}" if doi else "")
    return {"id":item["id"],"title":item["title"],"doi":doi,"authors":item["authors"],
        "publication":publication,
        "period":x["period"],"topic":x["topic"],"field":x.get("field",""),"kind":x["kind"],"source_status":"已核对公开摘要",
        "published_date":item["published_date"],"url":item["url"],"newness":x["newness"],
        "headline":x.get("headline",""),"core":x["core"],"evidence":[e["quote"] for e in x["evidence"]],"analysis":x["analysis"],
        "limits":x["limits"]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",default=today_local())
    p.add_argument("--input",default=str(ROOT/".cache/discovery.json"))
    p.add_argument("--dry-run",action="store_true")
    args=p.parse_args()
    data=json.loads(Path(args.input).read_text(encoding="utf-8"))
    if data["date"]!=args.date:raise ValueError("采集与审核日期不一致")
    records=data["records"]
    mode=os.environ.get("PUBLISH_MODE","auto_verified")
    if mode not in ("auto_verified","candidates_only"):raise ValueError("未知 PUBLISH_MODE")
    accepted=[];audit=[];seen=reviewed_keys();per={}
    limit=int(CONFIG.get("max_issue_items",7));per_limit=int(CONFIG.get("max_per_period",2))
    for i in sorted((x for x in records if x.get("kind") not in ("official_lead","wechat_lead")),key=lambda x:(-x["priority"],not bool(x.get("abstract"))))[:MAX_ATTEMPTS]:
        reason=""
        scope=assess(i.get("title",""),i.get("abstract",""),i.get("journal",""),i.get("kind",""))
        track=publication_track(scope)
        if is_duplicate(i,seen):reason="已经收录正式刊期"
        elif not scope["in_scope"]:reason="不在收录范围"
        elif not track:reason="未能归入所列时代"
        elif per.get(track,0)>=per_limit:reason=(f"{STANDALONE_GROUP}已有{per_limit}条" if track==STANDALONE_GROUP else f"同一时代已有{per_limit}条")
        elif i.get("kind") in ("journal_summary","journal_toc"):
            if not safe_public_url(i.get("url","")):reason="缺少原始链接"
            elif i["kind"]=="journal_toc":
                headline,zh=chinese_body(i)
                if not zh:reason="尚无中文说明"
                else:
                    extracted={"period":track,"topic":scope["field"] or track,"field":scope["field"],"headline":headline,
                        "core":zh,"analysis":zh[:180],"newness":"新发表目录","limits":"依据已公布的目录说明，未核对期刊正文",
                        "kind":genre(i["title"]),
                        "evidence":[{"quote":i["title"],"claim":i["title"]}]}
                    record=to_record(i,extracted);record["source_status"]="已核对公开摘要"
                    accepted.append((i,record,extracted));add_seen(i,seen)
                    per[track]=per.get(track,0)+1
            else:
                headline,zh=chinese_body(i)
                abstract=norm(i.get("abstract",""))
                found=sentences(abstract)
                if len(found)<2 and len(abstract)>=80:
                    mid=len(abstract)//2
                    found=[abstract[:mid],abstract[mid:mid+200]]
                if not zh:reason="尚无中文说明"
                elif len(found)<2:reason="出版社说明不足两条"
                else:
                    extracted={"period":track,"topic":scope["field"] or track,"field":scope["field"],"headline":headline,
                        "core":zh,"analysis":found[-1][:180],"newness":"新发表研究","limits":"依据出版社出刊页的说明，未核对期刊正文",
                        "kind":genre(i["title"]),
                        "evidence":[{"quote":clip_quote(found[0]),"claim":clip_quote(found[0])},{"quote":clip_quote(found[-1]),"claim":clip_quote(found[-1])}]}
                    accepted.append((i,to_record(i,extracted),extracted));add_seen(i,seen)
                    per[track]=per.get(track,0)+1
        elif len(norm(i.get("abstract","")))<MIN_ABSTRACT_CHARS:reason="正式摘要不足160字"
        else:
            headline,zh=chinese_body(i)
            if not zh:reason="尚无中文说明"
            else:
                extracted=excerpt_extract(i)
                valid,reason=validate_extract(extracted,i)
                if valid:
                    extracted["period"]=track
                    extracted["topic"]=scope["field"] or track
                    extracted["field"]=scope["field"]
                    extracted["headline"]=headline
                    extracted["core"]=zh
                    accepted.append((i,to_record(i,extracted),extracted))
                    add_seen(i,seen)
                    per[track]=per.get(track,0)+1
                    reason=""
        if reason:audit.append({"id":i["id"],"title":i["title"],"result":"rejected","reason":reason})
        if len(accepted)>=limit:break
    for i in records:
        if i.get("kind")=="official_lead":
            audit.append({"id":i["id"],"title":i["title"],"result":"lead_only","reason":"仅有机构页面线索，待核对正式报告或出版社摘要"})
    for i,r,x in accepted:
        audit.append({"id":i["id"],"title":i["title"],"result":"accepted","doi":i["doi"],
            "abstract_hash":hashlib.sha256(norm(i["abstract"]).encode()).hexdigest(),
            "support_hashes":[hashlib.sha256(norm(e["quote"]).encode()).hexdigest() for e in x["evidence"]]})
    newly=0
    path=ROOT/"content/issues"/f"{args.date}.json"
    if mode=="auto_verified" and not args.dry_run and accepted and not path.exists():
        dump_json(path,{"id":args.date,"issue_no":"研究周刊 · "+args.date,"date":args.date,
            "period":f"{data['window']['start']} — {data['window']['end']}","is_sample":False,
            "intro":"",
            "records":[r for _,r,_ in accepted]})
        newly=len(accepted)
    if not args.dry_run:
        dump_json(ROOT/"content/status.json",{"date":args.date,"mode":mode,"source_window":data.get("window",{}),
            "candidates":len(records),"qualified_recommendations":len(accepted),"published":newly,
            "warnings":data.get("warnings",[]),
            "message":"已发布新一期。" if newly else "本次没有发表。"})
        dump_json(ROOT/"content/audits"/f"{args.date}.json",{"date":args.date,"checks":audit})
    print(f"处理{len(records)}条，符合基础校验{len(accepted)}条，新发布{newly}条")
if __name__=="__main__":main()
