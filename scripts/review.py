"""Import model drafts with source mapping and final-text review records."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from editorial import digest, prepare_packet, validate_record, validate_issue
from research_core import CONFIG, ROOT, STANDALONE_GROUP, add_seen, dump_json, is_duplicate, reviewed_keys, today_local

def publication_track(scope):
    return STANDALONE_GROUP if scope.get('field')==STANDALONE_GROUP else scope.get('period') or ''

def run(data, drafts, approvals, *, root=ROOT, publish=False):
    if publish and data.get('synthetic'):raise ValueError('离线测试材料不可发布')
    packet=prepare_packet(data)
    draft_by={r['id']:r for r in drafts.get('records',[])}
    if len(draft_by)!=len(drafts.get('records',[])):raise ValueError('模型稿中存在重复标识')
    if set(draft_by)-{i['candidate']['id'] for i in packet['items']}:raise ValueError('模型稿含本次采集以外的标识')
    accepted=[];checks=[];seen=reviewed_keys();per={}
    for item in packet['items']:
        c=item['candidate'];r=draft_by.get(c['id']);result='waiting_for_draft';reason='已取得材料，待模型撰写'
        if is_duplicate(c,seen):result,reason='duplicate','已收入正式刊期'
        elif not item['sources']:result,reason='waiting_for_source','仅有题录或线索，须取得摘要或全文'
        elif r is not None:
            try:
                if any(r.get(k,'')!=c.get(k,'') for k in ('title','doi','url','published_date')):raise ValueError('稿件书目与采集记录不一致')
                approval=approvals.get('records',{}).get(c['id'],{})
                validate_record(r,packet=item,approval=approval,root=root)
                if len(accepted)>=CONFIG['max_issue_items'] or per.get(r['period'],0)>=CONFIG['max_per_period']:
                    result,reason='qualified_not_selected','稿件已复核，本期篇数或分组达到上限'
                else:
                    r=dict(r,review=approval);accepted.append(r);add_seen(r,seen);per[r['period']]=per.get(r['period'],0)+1
                    result,reason='accepted','最终正文与所列材料已完成复核'
            except (ValueError,KeyError,TypeError) as exc:result,reason='needs_review',str(exc)
        checks.append({'id':c['id'],'title':c['title'],'result':result,'reason':reason})
    issue=None
    if accepted:
        issue={'id':data['date'],'date':data['date'],'issue_no':'考古-周刊 · '+data['date'],'period':f"{data['window']['start']} — {data['window']['end']}",'intro':drafts.get('intro') or '本期编选新公布的考古材料与研究，说明主要发现、作者解释及其证据范围。','is_sample':False,'records':accepted}
        validate_issue(issue,root=root)
    target=root/'content/issues'/f"{data['date']}.json";published=0
    if publish and issue:
        if target.exists():raise ValueError('同日刊期已存在，更正须单独复核')
        dump_json(target,issue);published=len(accepted)
    state='published' if published else 'ready' if accepted else 'awaiting_editorial' if checks else 'discovery_finished'
    messages={'published':'已发布完成复核的新刊期。','ready':'稿件已完成复核，尚未发布。','awaiting_editorial':'候选材料已登记，待取得原文、撰写或复核。','discovery_finished':'本次采集已结束，请结合来源覆盖记录判断检索范围。'}
    audit={'date':data['date'],'checks':checks,'packet_digest':digest(packet)}
    status={'date':data['date'],'state':state,'mode':'reviewed_drafts','source_window':data['window'],'candidates':len(checks),'qualified_recommendations':len(accepted),'published':published,'warnings':data.get('warnings',[]),'coverage':data.get('coverage',[]),'message':messages[state]}
    previous=sorted((root/'content/issues').glob('*.json'),reverse=True)
    if previous:
        latest=json.loads(previous[0].read_text())
        status['latest_issue']={'id':latest['id'],'records':len(latest['records']),'window':latest['period']}
    return issue,audit,status

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',default=str(ROOT/'.cache/discovery.json'));p.add_argument('--date',default=today_local())
    p.add_argument('--drafts',help='模型稿JSON，标题及每段须对应来源片段');p.add_argument('--review-file',help='针对最终正文的独立复核记录')
    p.add_argument('--publish',action='store_true');p.add_argument('--dry-run',action='store_true');args=p.parse_args()
    data=json.loads(Path(args.input).read_text())
    if data['date']!=args.date:raise ValueError('采集日期与导入日期不一致')
    drafts=json.loads(Path(args.drafts).read_text()) if args.drafts else {}
    approvals=json.loads(Path(args.review_file).read_text()) if args.review_file else {}
    if args.publish and (not args.drafts or not args.review_file):raise ValueError('发布须提供模型稿及最终正文复核文件')
    issue,audit,status=run(data,drafts,approvals,publish=args.publish and not args.dry_run)
    if not args.dry_run:
        dump_json(ROOT/'content/audits'/f'{args.date}.json',audit);dump_json(ROOT/'content/status.json',status)
    print(status['message']+f" 候选{status['candidates']}条，完成复核{status['qualified_recommendations']}条，发布{status['published']}条。")
if __name__=='__main__':main()
