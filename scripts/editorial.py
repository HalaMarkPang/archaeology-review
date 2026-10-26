"""Publication contract. Structural checks do not replace source review."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from research_core import CONFIG, ROOT, STANDALONE_GROUP, canonical_doi, dump_json, issue_limit, norm, safe_public_url, slug
from publication_window import publication_membership

REVIEW_CHECKS = ("claims_supported", "uncertainty_preserved", "scope_confirmed", "sources_checked")
REQUIRED = ("id", "title", "authors", "publication", "published_date", "source_status", "core", "significance", "limits", "url", "period", "kind", "material_type")
LEVELS = {"已核对公开摘要", "已核对全文", "已核对会议纪要", "已核对新闻披露", "已核对报刊文章"}

def digest(value):
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()

def record_digest(record):
    return digest({k:v for k,v in record.items() if k != "review"})

def blocks(record):
    return ([record["headline"]] if record.get("headline") else [])+[x.strip() for key in ("core", "significance") for x in record[key].split("\n\n") if x.strip()]

def validate_record(record, *, packet=None, approval=None, root=ROOT, legacy=None):
    for key in REQUIRED:
        if not isinstance(record.get(key),str) or not record[key].strip():
            raise ValueError(f"缺少有效字段 {key}: {record.get('id','unknown')}")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+",record["id"]):raise ValueError("条目标识无效")
    if record["kind"] not in CONFIG["genres"]:raise ValueError("体裁不在配置中")
    if record["period"] not in [x["label"] for x in CONFIG["periods"]]+[STANDALONE_GROUP]:raise ValueError("时代或独立分组不在配置中")
    if record["source_status"] not in LEVELS:raise ValueError("目录材料或未知核验程度不可发布")
    if packet is not None:
        required_material={"已核对全文":"全文","已核对会议纪要":"会议纪要","已核对新闻披露":"新闻披露","已核对报刊文章":"报刊文章"}.get(record["source_status"])
        if required_material and not any(s.get("material_type")==required_material for s in packet.get("sources",[])):
            raise ValueError("所列核验程度超出本次取得的材料")
    if not safe_public_url(record["url"]):raise ValueError("原文地址无效")
    stamp=record["published_date"]
    if not re.fullmatch(r"\d{4}(?:-\d{2})?(?:-\d{2})?",stamp):raise ValueError("发表日期格式无效")
    date.fromisoformat(stamp+("-01-01" if len(stamp)==4 else "-01" if len(stamp)==7 else ""))
    for key in ("core", "significance"):
        if not re.search(r"[\u4e00-\u9fff]",record[key]):raise ValueError(f"缺少中文正文: {key}")
        if any(not x.strip() for x in record[key].split("\n\n")):raise ValueError(f"正文包含空段: {key}")
    if not record.get("evidence"):raise ValueError("缺少证据说明")
    significance_review=record.get("significance_review",{})
    if not isinstance(significance_review,dict):raise ValueError("研究意义复核记录无效")
    if significance_review.get("basis_title") and not safe_public_url(significance_review.get("basis_url","")):raise ValueError("研究意义补充来源无效")
    for im in record.get("images",[]):
        src=Path(im.get("src",""))
        if src.is_absolute() or ".." in src.parts or not (root/src).is_file():raise ValueError("图片路径无效")
        if any(not im.get(k) for k in ("alt","caption","source_url")) or not safe_public_url(im["source_url"]):raise ValueError("图片缺少来源或图注")
    if legacy is not None:
        if legacy.get(record["id"])!=record_digest(record):raise ValueError("历史正文已变化，须更新复核依据")
        return
    claims=record.get("claims",[])
    if [x.get("text") for x in claims]!=blocks(record):raise ValueError("标题或正文段落未完整映射证据")
    for claim in claims:
        if not claim.get("supports"):raise ValueError("正文断言缺少来源")
        for support in claim["supports"]:
            quote=norm(support.get("quote",""))
            if not 12<=len(quote)<=240 or not safe_public_url(support.get("url","")) or not support.get("source_hash"):raise ValueError("证据片段或来源无效")
            if packet is not None and not any(support["url"]==s.get("url") and support["source_hash"]==digest(norm(s.get("text",""))) and quote in norm(s.get("text","")) for s in packet.get("sources",[])):
                raise ValueError("证据片段不在本次来源材料中")
    if not all(record.get("generation",{}).get(k) for k in ("model","prompt_version","generated_at")):raise ValueError("缺少模型撰写记录")
    check=approval if approval is not None else record.get("review",{})
    if check.get("status")!="reviewed" or check.get("record_digest")!=record_digest(record):raise ValueError("缺少最终正文复核，或审后正文已变化")
    if not all(check.get(k) is True for k in REVIEW_CHECKS):raise ValueError("断言、推测程度、范围或来源尚未完成复核")
    if check.get("reviewer_type") not in ("model","human") or not check.get("reviewer") or not check.get("reviewed_at"):raise ValueError("缺少复核执行记录")

def validate_issue(issue, *, root=ROOT):
    for key in ("id","date","period","records","intro"):
        if key not in issue:raise ValueError(f"刊期缺少{key}")
    date.fromisoformat(issue["id"]);date.fromisoformat(issue["date"])
    start,end=re.split(r"\s*[—–]\s*",issue["period"])
    if date.fromisoformat(start)>date.fromisoformat(end):raise ValueError("刊期窗口倒置")
    window=issue.get("source_window",{})
    if window and (window.get("start")!=start or window.get("end")!=end):raise ValueError("刊期日期与发表窗口不一致")
    if not issue["records"]:raise ValueError("正式刊期不能没有正文")
    legacy=None
    if issue.get("legacy_migration"):
        migration=json.loads((root/"content/migrations"/f"{issue['id']}.json").read_text())
        if migration.get("issue_digest")!=digest(issue):raise ValueError("历史刊期已变化，须重新核对")
        legacy=migration["records"]
    elif (cap:=issue_limit("max_issue_items")) is not None and len(issue["records"])>cap:raise ValueError("普通刊期超出篇数上限")
    group_cap=issue_limit("max_per_period")
    ids=set();titles=set();dois=set();per={}
    for r in issue["records"]:
        validate_record(r,root=root,legacy=legacy)
        if window and publication_membership(r,window)!="inside":raise ValueError("实际发表时间未确认在本期窗口内")
        title=slug(r["title"]);doi=canonical_doi(r.get("doi",""))
        if r["id"] in ids or title in titles or (doi and doi in dois):raise ValueError("同一期存在重复作品")
        ids.add(r["id"]);titles.add(title)
        if doi:dois.add(doi)
        if r["published_date"][:7]<start[:7] or r["published_date"][:7]>end[:7] or (len(r["published_date"])==10 and not start<=r["published_date"]<=end):raise ValueError("发表日期不在刊期窗口内")
        per[r["period"]]=per.get(r["period"],0)+1
        if legacy is None and group_cap is not None and per[r["period"]]>group_cap:raise ValueError("同组条目超出上限")

def prepare_packet(data):
    items=[]
    for item in data["records"]:
        text=item.get("abstract","")
        sources=[{"url":item["url"],"text":text,"source_hash":digest(norm(text)),"material_type":"公开摘要"}] if text else []
        for source in item.get("source_materials",[]):
            if source.get("material_type") not in ("公开摘要","全文","会议纪要","新闻披露","报刊文章") or not source.get("text") or not safe_public_url(source.get("url","")):
                raise ValueError("补充原文材料无效；目录不能充当摘要或全文")
            sources.append(dict(source,source_hash=digest(norm(source["text"]))))
        items.append({"candidate":item,"sources":sources,"stage":"待撰写" if sources else "待取得原文"})
    return {"date":data["date"],"window":data["window"],"synthetic":data.get("synthetic",False),"items":items}

def main():
    p=argparse.ArgumentParser(description="导出模型撰写所需的本地证据包；不调用外部模型")
    p.add_argument("--input",default=str(ROOT/".cache/discovery.json"));p.add_argument("--out",default=str(ROOT/".cache/editorial-packet.json"))
    args=p.parse_args();packet=prepare_packet(json.loads(Path(args.input).read_text()));dump_json(Path(args.out),packet)
    print(f"已导出{len(packet['items'])}条材料；按编选规范撰写并复核后导入。")

if __name__=="__main__":main()
