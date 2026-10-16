"""Publication and collection regressions based on the audit failure cases."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build
import discover
import review
from editorial import REVIEW_CHECKS, digest, record_digest, prepare_packet, validate_record, validate_issue
from research_core import assess,norm

class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.text='The authors studied two Western Zhou bronze vessels. Their origin may be local, but a precise workshop attribution remains uncertain.'
        self.item={'id':'test-work','doi':'10.1234/test','title':'Western Zhou bronze vessels','authors':'Fixture Author','journal':'Early China','published_date':'2026-10-16','url':'https://doi.org/10.1234/test','kind':'journal-article','abstract':self.text,'priority':12}
        self.record={**{k:self.item[k] for k in ('id','doi','title','authors','published_date','url')},'publication':'Early China，2026-10-16','period':'商周','kind':'研究论文','material_type':'期刊论文','source_status':'已核对公开摘要','limits':'仅核对公开摘要，未核对全文。','headline':'西周铜器的来源比较','core':'研究比较了两件西周铜器。\n\n作者认为，它们可能来自本地，具体作坊仍不确定。','evidence':['比较对象为两件西周铜器。'],'generation':{'model':'fixture-model','prompt_version':'fixture-v1','generated_at':'2026-10-16'}}
        support={'quote':self.text,'url':self.item['url'],'source_hash':digest(norm(self.text))}
        self.record['claims']=[{'text':text,'supports':[dict(support)]} for text in [self.record['headline']]+self.record['core'].split('\n\n')]
        self.approval={**{k:True for k in REVIEW_CHECKS},'status':'reviewed','reviewer':'fixture-reviewer','reviewer_type':'model','reviewed_at':'2026-10-16','record_digest':record_digest(self.record)}
        self.packet={'sources':[{'url':self.item['url'],'text':self.text}]}
        self.data={'date':'2026-10-16','window':{'start':'2026-09-17','end':'2026-10-16'},'records':[self.item]}
    def test_final_review_accepts_mapped_record(self):
        validate_record(self.record,packet=self.packet,approval=self.approval)
    def test_genuine_quote_does_not_authorize_unreviewed_body(self):
        bad=copy.deepcopy(self.record);bad['core']='本文凭空宣称发现一位新帝王，在位六十年。';bad['claims']=[{'text':bad['headline'],'supports':bad['claims'][0]['supports']},{'text':bad['core'],'supports':bad['claims'][0]['supports']}]
        with self.assertRaisesRegex(ValueError,'复核'):validate_record(bad,packet=self.packet)
    def test_change_after_review_invalidates_approval(self):
        bad=copy.deepcopy(self.record);bad['core']=bad['core'].replace('可能','确定');bad['claims'][-1]['text']=bad['core'].split('\n\n')[-1]
        with self.assertRaisesRegex(ValueError,'审后'):validate_record(bad,packet=self.packet,approval=self.approval)
    def test_title_requires_evidence_mapping(self):
        bad=copy.deepcopy(self.record);bad['claims']=bad['claims'][1:]
        with self.assertRaisesRegex(ValueError,'完整映射'):validate_record(bad,packet=self.packet,approval=self.approval)
    def test_fabricated_source_quote_rejected(self):
        bad=copy.deepcopy(self.record);bad['claims'][0]['supports'][0]['quote']='A statement not contained in the source material.'
        with self.assertRaisesRegex(ValueError,'不在本次'):validate_record(bad,packet=self.packet,approval=self.approval)
    def test_toc_cannot_be_promoted_by_having_a_draft(self):
        data=copy.deepcopy(self.data);data['records'][0]['abstract']='';data['records'][0]['kind']='journal_toc'
        with patch.object(review,'reviewed_keys',return_value=set()):
            issue,audit,status=review.run(data,{'records':[self.record]},{'records':{'test-work':self.approval}})
        self.assertIsNone(issue);self.assertEqual(audit['checks'][0]['result'],'waiting_for_source')
    def test_english_without_draft_is_waiting_not_rejected(self):
        with patch.object(review,'reviewed_keys',return_value=set()):issue,audit,status=review.run(self.data,{}, {})
        self.assertEqual(audit['checks'][0]['result'],'waiting_for_draft');self.assertEqual(status['state'],'awaiting_editorial')
    def test_every_candidate_is_audited_after_twenty_duplicates(self):
        data=copy.deepcopy(self.data);data['records']=[dict(self.item,id=f'old-{n}',title=f'old {n}') for n in range(20)]+[self.item]
        with patch.object(review,'reviewed_keys',return_value=set()),patch.object(review,'is_duplicate',side_effect=lambda r,s:r['id'].startswith('old-')):
            issue,audit,status=review.run(data,{'records':[self.record]},{'records':{'test-work':self.approval}})
        self.assertEqual(len(audit['checks']),21);self.assertEqual(len(issue['records']),1)
    def test_synthetic_material_cannot_publish(self):
        with self.assertRaisesRegex(ValueError,'测试材料'):review.run(dict(self.data,synthetic=True),{}, {},publish=True)
    def test_publish_import_to_temporary_directory(self):
        with tempfile.TemporaryDirectory() as td,patch.object(review,'reviewed_keys',return_value=set()):
            issue,audit,status=review.run(self.data,{'records':[self.record]},{'records':{'test-work':self.approval}},root=Path(td),publish=True)
            self.assertEqual(status['published'],1);self.assertTrue((Path(td)/'content/issues/2026-10-16.json').exists())
    def test_missing_review_check_cannot_publish(self):
        bad=dict(self.approval,uncertainty_preserved=False)
        with self.assertRaisesRegex(ValueError,'尚未'):validate_record(self.record,packet=self.packet,approval=bad)
    def test_abstract_cannot_be_labelled_full_text(self):
        with self.assertRaisesRegex(ValueError,'超出'):validate_record(dict(self.record,source_status='已核对全文'),packet=self.packet,approval=self.approval)
    def test_verified_additional_source_unblocks_toc_material(self):
        data=copy.deepcopy(self.data);c=data['records'][0];c['abstract']='';c['kind']='journal_toc'
        c['source_materials']=[{'url':c['url'],'text':self.text,'material_type':'公开摘要'}]
        with patch.object(review,'reviewed_keys',return_value=set()):
            issue,audit,status=review.run(data,{'records':[self.record]},{'records':{'test-work':self.approval}})
        self.assertEqual(audit['checks'][0]['result'],'accepted')
    def test_unknown_genre_rejected(self):
        with self.assertRaisesRegex(ValueError,'体裁'):validate_record(dict(self.record,kind='不存在的体裁'))
    def test_same_doi_different_title_rejected_at_build(self):
        one=dict(self.record,review=self.approval);two=copy.deepcopy(one);two['id']='second';two['title']='Different title';two['review']['record_digest']=record_digest(two)
        # Replace the individual check to isolate issue-level DOI identity.
        with patch('editorial.validate_record'):
            with self.assertRaisesRegex(ValueError,'重复作品'):validate_issue({'id':'2026-10-16','date':'2026-10-16','period':'2026-10-01 — 2026-10-16','records':[one,two],'intro':'两篇比较'},root=Path('/tmp'))
    def test_empty_body_paragraph_rejected(self):
        with self.assertRaisesRegex(ValueError,'空段'):validate_record(dict(self.record,core='中文第一段\n\n\n\n中文末段'))
    def test_cross_year_display_has_years(self):
        self.assertEqual(build.display_span('2025-12-30 — 2026-01-05'),'2025年12月30日—2026年1月5日')

class CollectionRegressions(unittest.TestCase):
    def test_crossref_second_page_is_consumed(self):
        payloads=[{'message':{'items':[{'n':1},{'n':2}],'next-cursor':'second'}},{'message':{'items':[{'n':3}],'next-cursor':'end'}}]
        with patch.dict(discover.CONFIG,{'api_page_size':2,'api_max_pages':5}),patch.object(discover,'get_json',side_effect=payloads) as get:
            warnings=[];rows=list(discover.api_pages('https://example.org',{},'Crossref','fixture',warnings))
        self.assertEqual(len(rows),3);self.assertEqual(get.call_args_list[1].args[1]['cursor'],'second');self.assertEqual(warnings,[])
    def test_cursor_budget_is_explicitly_partial(self):
        with patch.dict(discover.CONFIG,{'api_page_size':1,'api_max_pages':1}),patch.object(discover,'get_json',return_value={'message':{'items':[{}],'next-cursor':'more'}}):
            warnings=[];list(discover.api_pages('https://example.org',{},'Crossref','fixture',warnings))
        self.assertIn('page_budget',warnings[0])
    def test_openalex_second_page_and_no_key_in_errors(self):
        payloads=[{'results':[1], 'meta':{'next_cursor':'more'}},{'results':[],'meta':{'next_cursor':None}}]
        with patch.dict(discover.CONFIG,{'api_page_size':1}),patch.object(discover,'get_json',side_effect=payloads):self.assertEqual(list(discover.api_pages('https://example.org',{},'OpenAlex','q',[])),[1])
        self.assertNotIn('sensitive-value',discover.error_message(ValueError('https://api.openalex.org?api_key=sensitive-value&x=2')))
    def test_unparsed_wechat_is_never_complete(self):
        with patch.dict(discover.CONFIG,{'wechat_accounts':[{'name':'考古陕西'}]}):
            leads,coverage=discover.collect_wechat_accounts(date(2026,9,1),date(2026,10,16),[],fetch=lambda q,p:'<html>请稍后重试</html>')
        self.assertEqual(coverage[0]['status'],'未核完');self.assertIn('页面未识别',coverage[0]['error'])
    def test_old_search_hit_does_not_stop_unsorted_results(self):
        page=[({'title':'old','published':date(2025,1,1),'account':'A','href':''}),({'title':'new','published':date(2026,10,1),'account':'A','href':''})]
        c=discover.wechat_coverage('A',[(page,False)],date(2026,9,1),date(2026,10,16))
        self.assertEqual([x['title'] for x in c['articles']],['new']);self.assertEqual(c['status'],'未核完')
    def test_account_substring_does_not_match(self):
        row={'title':'唐墓','published':date(2026,10,1),'account':'考古陕西札记','href':''}
        c=discover.wechat_coverage('考古陕西',[([row],False)],date(2026,9,1),date(2026,10,16));self.assertEqual(c['articles'],[])
    def test_dedupe_merges_title_with_and_without_doi(self):
        one={'id':'a','doi':'10.1234/yes','title':'Same title','published_date':'2026-10-16','kind':'journal-article','priority':1,'abstract':''};two=dict(one,id='b',doi='',abstract='available')
        rows=discover.dedupe([one,two],set(),date(2026,9,1),date(2026,10,16))
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['doi'],'10.1234/yes');self.assertTrue(rows[0]['abstract'])
    def test_applied_settlement_stays_material_study(self):
        x=assess('Topographic accessibility and proto-urban settlement organization in Neolithic China','Georeferenced sites and terrain are compared.','Nature Cities')
        self.assertEqual(x['period'],'新石器');self.assertNotEqual(x['field'],'考古学理论')
    def test_general_theory_is_not_forced_to_china(self):
        x=assess('Archaeology is culture history, or it is nothing','Culture history is an overarching framework for archaeological practice.','Journal of Anthropological Archaeology')
        self.assertTrue(x['in_scope']);self.assertEqual(x['field'],'考古学理论')
    def test_qing_is_explicitly_excluded_in_core_journal(self):
        self.assertFalse(assess('清代景德镇瓷器研究','清代瓷器。','考古')['in_scope'])
    def test_early_modern_humans_are_not_excluded_as_modern_history(self):
        self.assertTrue(assess('旧石器时代早期现代人','中国旧石器遗址。','考古')['in_scope'])
    def test_ming_qing_comparative_material_is_retained(self):
        self.assertTrue(assess('明清瓷器比较','明清瓷器。','考古')['in_scope'])
    def test_toc_without_dynasty_is_retained(self):
        text='本期目录\n唐进贤冠貂蝉试释\n叶炜\n精彩摘要\n下期要目\n《文物》2026年第9期\n出版日期：2026年9月25日'
        self.assertEqual(len(discover.wenwu_records(text,'https://www.wenwu.com/x')),1)
    def test_complete_author_list_preserved(self):
        raw={'DOI':'10.1234/x','title':['Neolithic China'],'author':[{'family':str(n)} for n in range(12)]}
        self.assertEqual(len(discover.from_crossref(raw)['authors'].split(', ')),12)

if __name__=='__main__':unittest.main()
