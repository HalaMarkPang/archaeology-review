"""Deterministic local checks; do not prove third-party API access."""
import sys,unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from research_core import CONFIG,assess,stable_id,safe_public_url
from build import display_span
from discover import from_crossref,abstract_openalex,dedupe,wenwu_records,wechat_coverage,parse_wechat_html
from review import publication_track
class DiscoveryTests(unittest.TestCase):
    def test_crossref(self):
        raw={"DOI":"10.1234/ABCD","title":["Bronze inscriptions in Western Zhou"],
             "container-title":["Early China"],"author":[{"given":"A","family":"B"}],
             "published-online":{"date-parts":[[2026,10,9]]},"type":"journal-article",
             "abstract":"<jats:p>Western Zhou bronze inscriptions are examined.</jats:p>"}
        x=from_crossref(raw)
        self.assertEqual(x["published_date"],"2026-10-09")
        self.assertEqual(x["doi"],"10.1234/abcd")
        self.assertIn("Western Zhou",x["abstract"])
    def test_openalex(self):self.assertEqual(abstract_openalex({"Bronze":[0],"inscriptions":[1],"found":[2]}),"Bronze inscriptions found")
    def test_dedup(self):
        item={"doi":"10.1234/yes","title":"Western Zhou bronze inscriptions","abstract":"new evidence",
              "journal":"Early China","published_date":"2026-10-10","kind":"journal-article",
              "url":"https://doi.org/10.1234/yes","priority":22}
        item["id"]=stable_id(item["doi"],item["title"])
        self.assertEqual(len(dedupe([item,dict(item)],set(),date(2026,9,15),date(2026,10,14))),1)
        self.assertEqual(len(dedupe([item],{"doi:10.1234/yes"},date(2026,9,15),date(2026,10,14))),1)  # Audit retains duplicates.
    def test_url(self):
        self.assertTrue(safe_public_url("https://doi.org/10.123/xxx"))
        self.assertFalse(safe_public_url("http://localhost/test"))
        self.assertTrue(safe_public_url("http://kaogu.cssn.cn/xsqy/xskw/kg/"))
        self.assertFalse(safe_public_url("file:///etc/passwd"))
    def test_scope_requires_a_period_or_field(self):
        turkic=assess("On Some Countries in the Köl Tegin and Bilga Qagan Inscriptions","Old Turkic inscriptions and Chinese historical sources.","History Studies")
        self.assertFalse(turkic["in_scope"])
        self.assertEqual(turkic["score"],0)
        yuan=assess("Abbots’ Stele Inscriptions of Yuan-Dynasty Jiangnan","Stele inscriptions of Chan abbots.","Religions")
        self.assertTrue(yuan["in_scope"])
        self.assertEqual(yuan["period"],"宋元明")
        zhou=assess("Western Zhou bronze inscriptions","Oracle bones are not discussed.","Early China")
        self.assertEqual(zhou["period"],"商周")
        self.assertGreaterEqual(zhou["score"],8)
        qing=assess("Qing dynasty porcelain","Archaeology of the Qing court.","Orientations")
        self.assertFalse(qing["in_scope"])
        europe=assess("Magdalenian adhesive from Poland","Upper Paleolithic composite adhesive.","Archaeometry")
        self.assertFalse(europe["in_scope"])
        report=assess("西安南郊一座砖室墓发掘简报","出土器物若干。","考古")
        self.assertTrue(report["in_scope"])
        self.assertEqual(report["period"],"")
        liao=assess("医巫闾山辽陵研究的几个问题","辽代帝陵分显陵和乾陵。","文物")
        self.assertTrue(liao["in_scope"])
        self.assertEqual(liao["period"],"宋元明")
    def test_wenwu_issue_page_keeps_blurbs_and_titled_entries(self):
        text="""本期目录
·考古新收获·
四川成都双元村墓地Ⅰ区战国墓发掘简报
成都市文物考古研究院
山西临汾中大街元墓（M19）发掘简报
山西大学考古文博学院等
医巫闾山辽陵研究的几个问题
董新林
精彩摘要
四川成都双元村墓地Ⅰ区战国墓发掘简报
2016年3月至2018年7月，成都文物考古研究院等单位对成都市青白江区双元村墓地进行了抢救性发掘，共清理270余座东周墓葬。墓地按发掘时间先后分为两个区域，其中Ⅰ区位于墓地东北部，墓葬年代多为战国时期。出土陶器有鼎、釜、罐，铜器有矛、剑、戈。根据墓葬形制及出土器物判断，这三座墓应为战国早、中期蜀国低级贵族墓葬。这三座墓葬的发掘为研究战国时期蜀文化变迁提供了重要资料。
下期要目
某简报
《文物》2026年第9期
出版日期：2026年9月25日
"""
        rows=wenwu_records(text,"https://www.wenwu.com/newsinfo/11340222.html")
        by={r["title"]:r for r in rows}
        self.assertIn("四川成都双元村墓地I区战国墓发掘简报",by)
        brief=by["四川成都双元村墓地I区战国墓发掘简报"]
        self.assertEqual(brief["kind"],"journal_summary")
        self.assertEqual(brief["period_guess"],"战国秦汉")
        self.assertIn("东周墓葬",brief["abstract"])
        self.assertEqual(brief["authors"],"成都市文物考古研究院")
        tomb=by["山西临汾中大街元墓(M19)发掘简报"]
        self.assertEqual(tomb["kind"],"journal_toc")
        self.assertEqual(tomb["period_guess"],"宋元明")
        self.assertEqual(by["医巫闾山辽陵研究的几个问题"]["period_guess"],"宋元明")
    def test_theory_ignores_period(self):
        scoped=assess("龙山时期的聚落考古","讨论考古学理论。","南方文物")
        self.assertEqual(scoped["field"],"考古学理论")
        self.assertEqual(scoped["period"],"新石器")
        self.assertEqual(publication_track(scoped),"考古学理论")
        plain=assess("比较视野下的考古学理论","不涉及具体遗址。","南方文物")
        self.assertEqual(plain["period"],"")
        self.assertTrue(plain["in_scope"])
        self.assertEqual(publication_track(plain),"考古学理论")
        foreign=assess("Archaeological theory of Neanderthal sites","A statistical approach.","Journal of Archaeological Method and Theory")
        self.assertTrue(foreign["in_scope"])  # General theory has an explicit international exception.
    def test_theory_toc_line_does_not_need_a_period(self):
        text="""本期目录
·研究与探索·
比较视野下的考古学理论
张三
精彩摘要
下期要目
《文物》2026年第9期
出版日期：2026年9月25日
"""
        rows=wenwu_records(text,"https://www.wenwu.com/newsinfo/11340222.html")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["field"],"考古学理论")
        self.assertEqual(rows[0]["period_guess"],"")
class WechatCoverageTests(unittest.TestCase):
    def test_unfinished_list_is_not_an_empty_account(self):
        pages=[([{"title":"唐墓发掘简报","published":date(2026,10,1),"account":"考古陕西","href":""}],True)]
        report=wechat_coverage("考古陕西",pages,date(2026,9,1),date(2026,10,14))
        self.assertEqual(report["status"],"未核完")
        self.assertEqual(len(report["articles"]),1)
    def test_finished_when_there_is_no_next_page(self):
        pages=[([{"title":"唐墓发掘简报","published":date(2026,10,1),"account":"考古陕西","href":""}],False)]
        report=wechat_coverage("考古陕西",pages,date(2026,9,1),date(2026,10,14))
        self.assertEqual(report["status"],"未核完")  # Exhausted search is not exhausted account history.
    def test_blocked_fetch_stays_unfinished(self):
        report=wechat_coverage("考古陕西",[],date(2026,9,1),date(2026,10,14),error="拦截")
        self.assertEqual(report["status"],"未核完")
        self.assertEqual(report["articles"],[])
    def test_parse_keeps_account_title_and_date(self):
        html='<ul class="news-list"><li><div class="txt-box"><h3><a href="https://weixin.sogou.com/link?url=abc">陕西西安唐墓发掘简报</a></h3><a class="account">考古陕西</a><span class="s2">2026-9-30</span></div></li></ul>'
        rows,has_next=parse_wechat_html(html,"考古陕西",date(2026,10,15))
        self.assertFalse(has_next)
        self.assertEqual(rows[0]["title"],"陕西西安唐墓发掘简报")
        self.assertEqual(rows[0]["published"],date(2026,9,30))
        self.assertEqual(rows[0]["account"],"考古陕西")
class ConfigTests(unittest.TestCase):
    def test_schedule_matches_workflow(self):
        text=(Path(__file__).resolve().parents[1]/".github/workflows/research.yml").read_text(encoding="utf-8")
        import re
        cron=re.search(r"cron:\s*'([^']+)'",text).group(1)
        zone=re.search(r"timezone:\s*'([^']+)'",text).group(1)
        self.assertEqual(cron,CONFIG["schedule"]["cron"])
        self.assertEqual(zone,CONFIG["schedule"]["timezone"])
    def test_display_span_comes_from_the_issue_window(self):
        self.assertEqual(display_span("2026-09-01 — 2026-10-14"),"9月1日—10月14日")
if __name__=="__main__":unittest.main()
