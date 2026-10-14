"""Deterministic local checks; do not prove third-party API access."""
import sys,unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from research_core import stable_id,safe_public_url
from discover import from_crossref,abstract_openalex,dedupe
from review import validate_extract
class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.abstract=("The excavated tomb included a bronze inscription identifying the named lineage. "
                       "Stratigraphic observations place the burial in the Western Zhou period. "
                       "The authors compare the excavated inscription with contemporaneous bronze vessels "
                       "to examine relationships among household groups in the Zhou region.")
        self.item=dict(doi="10.1234/ab.2026.33",url="https://doi.org/10.1234/ab.2026.33",abstract=self.abstract)
        self.output=dict(relevant=True,core="论文依据墓葬铭文与地层观察讨论西周墓葬及相关家族关系，并与其他青铜器铭文进行比较；具体结论仍须核对全文。",
            core_quote="The excavated tomb included a bronze inscription identifying the named lineage.",
            evidence=[
              {"claim":"摘要载明出土墓葬包含可辨识族系的青铜器铭文","quote":"The excavated tomb included a bronze inscription identifying the named lineage."},
              {"claim":"摘要指出地层观察将墓葬归入西周时期","quote":"Stratigraphic observations place the burial in the Western Zhou period."}],
            analysis="讨论家族关系",newness="新发表研究",period="商周",topic="青铜器铭文",kind="研究论文",limits="未查全文")
    def test_quote(self):self.assertTrue(validate_extract(self.output,self.item)[0])
    def test_fabricated_quote(self):
        self.output["evidence"][0]["quote"]="The excavation proves an unknown king reigned for sixty years."
        self.assertFalse(validate_extract(self.output,self.item)[0])
    def test_duplicate_quotes(self):
        self.output["evidence"][1]["quote"]=self.output["evidence"][0]["quote"]
        self.assertFalse(validate_extract(self.output,self.item)[0])
    def test_missing_doi(self):
        self.item["doi"]=""
        self.assertFalse(validate_extract(self.output,self.item)[0])
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
        self.assertEqual(dedupe([item],{"doi:10.1234/yes"},date(2026,9,15),date(2026,10,14)),[])
    def test_url(self):
        self.assertTrue(safe_public_url("https://doi.org/10.123/xxx"))
        self.assertFalse(safe_public_url("http://localhost/test"))
        self.assertFalse(safe_public_url("file:///etc/passwd"))
if __name__=="__main__":unittest.main()
