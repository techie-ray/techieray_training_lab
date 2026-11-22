"""URL matching: what counts as the same page."""
from techieray_training_lab.common.matching import fragment_for, url_matches


def test_url_matching_boundaries_and_variants():
    frag = fragment_for('https://www.congress.gov/bill/119th-congress/house-bill/45/')
    assert frag == 'congress.gov/bill/119th-congress/house-bill/45'
    assert url_matches('http://congress.gov/bill/119th-congress/house-bill/45/text', frag)
    assert not url_matches('https://www.congress.gov/bill/119th-congress/house-bill/4512', frag)


def test_matching_ignores_case_language_and_bill_address_forms():
    hansard = 'hansard.parliament.uk/commons/2026-11-04/debates/C55F/SmartGlasses'
    assert url_matches('https://hansard.parliament.uk/Commons/2026-11-04/debates/c55f/SmartGlasses', hansard)
    assert url_matches('https://www.mcmc.gov.my/en/media/press-releases/x', 'mcmc.gov.my/ms/media/press-releases/x')
    assert url_matches('https://example.gov/news/x?lang=fr', 'example.gov/news/x?lang=en')
    bill = 'congress.gov/bill/118th-congress/senate-bill/9876/text'
    assert url_matches('https://www.congress.gov/118/bills/s9876/BILLS-118s9876is.htm', bill)
    assert url_matches('https://www.govinfo.gov/content/pkg/BILLS-118s9876is/html/BILLS-118s9876is.htm', bill)
    assert url_matches('https://www.congress.gov/bill/118th-congress/senate-bill/9876/all-info', bill)
    assert not url_matches('https://www.congress.gov/118/bills/s46/BILLS-118s46is.htm', bill)
    assert not url_matches('https://www.congress.gov/bill/118th-congress/house-bill/9876', bill)


def test_matching_requires_the_same_host():
    frag = 'gov.il/pages/forum'
    assert not url_matches('https://www.president.gov.il/pages/forum', frag)
    assert not url_matches('https://example.com/?u=https://gov.il/pages/forum', frag)


def test_matching_federal_register_and_swiss_news_families():
    fr = 'govinfo.gov/content/pkg/FR-2025-09-26/pdf/2025-99001.pdf'
    assert url_matches('https://www.federalregister.gov/documents/2025/09/26/2025-99001/notice-of-request', fr)
    assert url_matches('https://www.federalregister.gov/d/2025-99001', fr)
    assert not url_matches('https://www.federalregister.gov/d/2025-18738', fr)
    assert url_matches('https://www.admin.ch/de/newnsb/ZQ12XyzAbCdE', 'bsv.admin.ch/fr/newnsb/ZQ12XyzAbCdE')
    assert not url_matches('https://www.admin.ch/de/newnsb/OTHER', 'bsv.admin.ch/fr/newnsb/ZQ12XyzAbCdE')


def test_hash_routes_identify_pages():
    frag = fragment_for('https://sprs.parl.gov.sg/search/#/fullreport?sittingdate=04-11-2026')
    assert url_matches('https://sprs.parl.gov.sg/search/#/fullreport?sittingdate=04-11-2026', frag)
    assert not url_matches('https://sprs.parl.gov.sg/search/#/fullreport?sittingdate=05-11-2026', frag)
    assert not url_matches('https://sprs.parl.gov.sg/search/', frag)
    assert url_matches('https://ico.org.uk/x#section-2', 'ico.org.uk/x')


def test_a_url_inside_a_query_string_is_not_the_address():
    frag = 'gov.ie/pdf/?file=https://assets.gov.ie/319531/abc.pdf'
    assert url_matches('https://www.gov.ie/pdf/?file=https://assets.gov.ie/319531/abc.pdf#page=null', frag)
    assert not url_matches('https://assets.gov.ie/319531/abc.pdf', frag)
    # an answer with no scheme that carries the official page in its query is still the other site
    assert not url_matches('evil.example/?u=https://ico.org.uk/x', 'ico.org.uk/x')
    assert not url_matches('news.example/redirect?to=http://ico.org.uk/x', 'ico.org.uk/x')


def test_trailing_slash_in_a_query_value_is_ignored():
    url = 'https://doc.msit.go.kr/viewer/doc.html?key=faeb&contextPath=/SynapDocViewServer/'
    assert url_matches(url, fragment_for(url))
    assert not url_matches('https://doc.msit.go.kr/viewer/doc.html?key=other&contextPath=/SynapDocViewServer/',
                           fragment_for(url))


def test_eurlex_celex_and_eli_are_one_act():
    eli = 'eur-lex.europa.eu/eli/reg/2024/1689'
    assert url_matches('https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689', eli)
    assert url_matches('https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX%3A32024R1689', eli)
    assert url_matches('https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng', eli)
    assert url_matches('https://eur-lex.europa.eu/eli/reg/2024/1689/oj', 'eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689')
    assert not url_matches('https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689R(01)', eli)
    assert not url_matches('https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679', eli)
    assert url_matches('https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32019L0790', 'eur-lex.europa.eu/eli/dir/2019/790')


def test_tracking_parameters_are_ignored_but_real_ones_kept():
    tagged = 'europarl.europa.eu/doceo/document/IMCO-PA-768056_EN.pdf?ref=eutechloop.com'
    assert url_matches('https://www.europarl.europa.eu/doceo/document/IMCO-PA-768056_EN.pdf', tagged)
    assert url_matches('https://cac.gov.cn/2026-04/28/c_1.htm', 'cac.gov.cn/2026-04/28/c_1.htm?mc_cid=37cf&mc_eid=03')
    assert url_matches('https://x.gov/a?id=5&utm_source=mail', 'x.gov/a?id=5')
    real = 'ec.europa.eu/transparency/documents-register/detail?ref=COM(2025)265&lang=en'
    assert not url_matches('https://ec.europa.eu/transparency/documents-register/detail?ref=COM(2025)266', real)
    assert url_matches('https://ec.europa.eu/transparency/documents-register/detail?ref=COM(2025)265', real)


def test_california_bill_tabs_are_one_bill():
    bill = 'leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260AB723'
    for tab in ('billTextClient', 'billStatusClient', 'billHistoryClient', 'billVersionsClient', 'billNavClient'):
        assert url_matches(f'https://leginfo.legislature.ca.gov/faces/{tab}.xhtml?bill_id=202520260AB723', bill), tab
    assert url_matches('https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?search_keywords=x&bill_id=202520260AB723', bill)
    # another bill, or a page that is not the bill (votes, committee analyses), is not the same page
    assert not url_matches('https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260AB7230', bill)
    assert not url_matches('https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260AB724', bill)
    assert not url_matches('https://leginfo.legislature.ca.gov/faces/billVotesClient.xhtml?bill_id=202520260AB723', bill)
    assert not url_matches('https://leginfo.legislature.ca.gov/faces/billAnalysisClient.xhtml?bill_id=202520260AB723', bill)


def test_camara_file_name_is_cosmetic():
    frag = 'camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3063060&filename=PL%206237/2025'
    assert url_matches('https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3063060', frag)
    assert url_matches('https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3063060&filename=Avulso+PL+6237/2025', frag)
    assert not url_matches('https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3104780', frag)
    # only on the Câmara: elsewhere a file name can name the document
    assert not url_matches('https://x.gov/download?filename=b.pdf', 'x.gov/download?filename=a.pdf')
