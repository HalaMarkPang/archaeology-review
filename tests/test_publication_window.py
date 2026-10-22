"""Weekly cutoff regressions, including date-only records on both Fridays."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import discover
import review
from editorial import REVIEW_CHECKS, blocks, digest, norm, record_digest, validate_issue
from publication_window import weekly_window, publication_membership

ZONE = ZoneInfo('Asia/Shanghai')


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.window = weekly_window('2026-10-23')

    def test_requested_friday_to_friday_noon(self):
        self.assertEqual(self.window['start_at'], '2026-10-16T12:00:00+08:00')
        self.assertEqual(self.window['end_at'], '2026-10-23T12:00:00+08:00')

    def test_friday_morning_uses_last_completed_window(self):
        result = weekly_window(now=datetime(2026,10,23,11,59,tzinfo=ZONE))
        self.assertEqual(result['end'], '2026-10-16')

    def test_noon_and_delayed_run_have_same_cutoff(self):
        for moment in (datetime(2026,10,23,12,tzinfo=ZONE), datetime(2026,10,24,18,tzinfo=ZONE)):
            self.assertEqual(weekly_window(now=moment), self.window)

    def test_thursday_does_not_invent_future_cutoff(self):
        result = weekly_window(now=datetime(2026,10,22,19,tzinfo=ZONE))
        self.assertEqual(result['end'], '2026-10-16')

    def test_cutoff_crosses_year(self):
        result = weekly_window('2027-01-01')
        self.assertEqual(result['start_at'], '2026-12-25T12:00:00+08:00')

    def test_replay_date_must_be_scheduled_friday(self):
        with self.assertRaisesRegex(ValueError, '周五'):
            weekly_window('2026-10-22')

    def test_start_exclusive_end_inclusive_and_timezone(self):
        cases = {
            '2026-10-16T12:00:00+08:00': 'outside',
            '2026-10-16T12:00:01+08:00': 'inside',
            '2026-10-23T12:00:00+08:00': 'inside',
            '2026-10-23T12:00:01+08:00': 'outside',
            '2026-10-23T04:00:00Z': 'inside',
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                row = {'published_at':value,'published_at_source':'https://example.org/paper'}
                self.assertEqual(publication_membership(row,self.window),expected)

    def test_boundary_date_and_low_precision_stay_unresolved(self):
        for value in ('2026-10-16','2026-10-23','2026-10','2026',''):
            self.assertEqual(publication_membership({'published_date':value},self.window),'needs_publication_time')
        self.assertEqual(publication_membership({'published_date':'2026-10-22'},self.window),'inside')

    def test_naive_or_unsourced_time_cannot_resolve_boundary(self):
        for row in (
            {'published_at':'2026-10-23T11:00:00+08:00'},
            {'published_at':'2026-10-23T11:00:00','published_at_source':'https://example.org/paper'},
            {'published_at':123,'published_at_source':'https://example.org/paper'},
        ):
            self.assertEqual(publication_membership(row,self.window),'needs_publication_time')

    def test_offline_discovery_writes_precise_window(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);fixture=root/'fixture.json';fixture.write_text('[]')
            with patch.object(discover,'ROOT',root),patch.object(sys,'argv',['discover.py','--date','2026-10-23','--offline-fixture',str(fixture)]):
                discover.main()
            local=json.loads((root/'.cache/discovery.json').read_text())
            public=json.loads((root/'content/candidates/2026-10-23.json').read_text())
            self.assertEqual(local['window'],self.window)
            self.assertEqual(public['window'],self.window)
            self.assertTrue(local['synthetic'])
            with patch.object(review,'ROOT',root),patch.object(sys,'argv',['review.py','--input',str(root/'.cache/discovery.json')]):
                review.main()
            self.assertTrue((root/'content/audits/2026-10-23.json').is_file())
            self.assertFalse((root/'content/audits/None.json').exists())


class PublicationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.text='The authors studied Western Zhou bronze vessels and compared their geographic origins.'
        self.item={'id':'weekly-work','doi':'10.1234/weekly','title':'Western Zhou bronze vessels','authors':'Fixture Author','journal':'Early China','published_date':'2026-10-22','url':'https://doi.org/10.1234/weekly','kind':'journal-article','abstract':self.text,'priority':12}
        self.record={**{k:self.item[k] for k in ('id','doi','title','authors','published_date','url')},'publication':'Early China','period':'商周','kind':'研究论文','material_type':'期刊论文','source_status':'已核对公开摘要','limits':'核对摘要。','headline':'西周铜器的来源','core':'研究比较西周铜器的地理来源。','significance':'这组材料可用于比较西周铜器的原料供应。','evidence':['摘要说明研究对象。'],'generation':{'model':'fixture','prompt_version':'fixture','generated_at':'2026-10-23'}}
        self.data={'date':'2026-10-23','window':weekly_window('2026-10-23'),'records':[self.item]}

    def run_review(self, day, at=None):
        item=dict(self.item,published_date=day)
        record=dict(self.record,published_date=day)
        if at:
            record.update(published_at=at,published_at_source=item['url'])
        support={'quote':self.text,'url':item['url'],'source_hash':digest(norm(self.text))}
        record['claims']=[{'text':text,'supports':[support]} for text in blocks(record)]
        approval={**{k:True for k in REVIEW_CHECKS},'status':'reviewed','reviewer':'fixture','reviewer_type':'model','reviewed_at':'2026-10-23','record_digest':record_digest(record)}
        with patch.object(review,'reviewed_keys',return_value=set()):
            return review.run(dict(self.data,records=[item]),{'records':[record]},{'records':{item['id']:approval}})

    def test_friday_date_without_time_is_not_published(self):
        issue,audit,status=self.run_review('2026-10-23')
        self.assertIsNone(issue)
        self.assertEqual(audit['checks'][0]['result'],'waiting_for_publication_time')

    def test_friday_after_cutoff_is_not_published(self):
        issue,audit,status=self.run_review('2026-10-23','2026-10-23T12:00:01+08:00')
        self.assertIsNone(issue)
        self.assertEqual(audit['checks'][0]['result'],'outside_window')

    def test_verified_noon_can_publish_and_build_rechecks_window(self):
        issue,audit,status=self.run_review('2026-10-23','2026-10-23T12:00:00+08:00')
        self.assertEqual(audit['checks'][0]['result'],'accepted')
        self.assertEqual(issue['source_window'],self.data['window'])
        validate_issue(issue)
        changed=copy.deepcopy(issue)
        changed['records'][0]['published_at']='2026-10-23T12:00:01+08:00'
        changed['records'][0]['review']['record_digest']=record_digest(changed['records'][0])
        with self.assertRaisesRegex(ValueError,'发表时间'):
            validate_issue(changed)


if __name__=='__main__':
    unittest.main()
