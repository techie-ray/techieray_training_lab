"""The regulatory research tasks are well formed, and the reward pays for their answers and nothing else."""
import json
from pathlib import Path

from techieray_training_lab.common import jsonl
from techieray_training_lab.common.matching import url_matches
from techieray_training_lab.regulatory_research.find_primary_source import find_primary_source_reward
from techieray_training_lab.regulatory_research.find_primary_source.cli import score_rollouts, summarise
from techieray_training_lab.regulatory_research.find_primary_source.checks import run

ROOT = Path(__file__).resolve().parent.parent
SET = ROOT / 'sets' / 'regulatory_research' / 'find_primary_source'
TASKS = jsonl.read(SET / 'data' / 'tasks.jsonl')
FIELDS = {'example_id', 'task', 'as_of_date', 'input', 'input_named', 'input_full', 'reference', 'strata'}


def test_tasks_are_well_formed():
    assert len(TASKS) == 50 and len({t['example_id'] for t in TASKS}) == 50
    assert sum(t['reference']['no_official_source'] for t in TASKS) == 5
    for t in TASKS:
        assert set(t) == FIELDS, t['example_id']
        assert t['task'] == 'find_primary_source'
        assert t['input']['headline'] and t['input']['jurisdictions']
        ref = t['reference']
        if ref['no_official_source']:
            assert ref['accepted_url_fragments'] == [] and ref['canonical_url'] is None
            assert t['strata']['question_form'] == 'counterfactual_alert' and not t['strata']['strict']
            continue
        assert ref['accepted_url_fragments']
        assert any(url_matches(ref['canonical_url'], f) for f in ref['accepted_url_fragments'])
        assert t['strata']['strict'] == bool(ref.get('authoritative_url_fragments'))


def test_every_reference_answer_scores_one():
    for t in TASKS:
        if t['reference']['no_official_source']:
            answer = {'url': None, 'no_official_source': True, 'confidence': 'verified'}
        else:
            answer = {'url': t['reference']['canonical_url'], 'confidence': 'verified'}
        assert find_primary_source_reward(t, answer).reward == 1.0, t['example_id']


def test_every_accepted_page_scores_one_unless_the_task_is_strict():
    for t in TASKS:
        ref = t['reference']
        for f in ref['accepted_url_fragments']:
            result = find_primary_source_reward(t, {'url': 'https://' + f, 'confidence': 'verified'})
            strict_text = any(url_matches('https://' + f, a) for a in ref.get('authoritative_url_fragments') or [])
            assert result.correct == (strict_text or not ref.get('authoritative_url_fragments')), (t['example_id'], f)


def test_no_shortcut_earns_reward_on_the_released_tasks():
    report = run(TASKS)['strategies']
    assert all(r['ok'] for r in report.values()), {k: v for k, v in report.items() if not v['ok']}


def test_example_rollouts_score_as_documented():
    rows = score_rollouts(TASKS, jsonl.read(SET / 'examples' / 'rollouts.jsonl'))
    assert [r['outcome'] for r in rows] == ['key', 'unlisted', 'no_source_wrong', 'key', 'no_source_correct', 'source_claimed']
    assert summarise(rows, 'key only')['rollouts'] == len(rows)


def test_shipped_reward_checks_match_a_fresh_run():
    shipped = json.loads((SET / 'results' / 'reward_checks.json').read_text())
    assert {k: v['mean_reward'] for k, v in shipped['strategies'].items()} == \
        {k: v['mean_reward'] for k, v in run(TASKS)['strategies'].items()}


def test_load_tasks_and_cli(capsys):
    from techieray_training_lab.regulatory_research.find_primary_source import load_tasks
    from techieray_training_lab.regulatory_research.find_primary_source.cli import main
    assert len(load_tasks()) == 50
    assert main(['score', '--rollouts', str(SET / 'examples' / 'rollouts.jsonl')]) == 0
    assert json.loads(capsys.readouterr().out)['rollouts'] == 6
    assert main(['check']) == 0


def test_task_prompt_puts_the_instrument_before_its_announcement():
    # strict tasks score only the text, so the prompt must never present an announcement as an equal answer
    prompt = (SET / 'data' / 'task_prompt.txt').read_text()
    assert 'whenever its text is published online' in prompt
    assert prompt.index('the instrument itself') < prompt.index('announcement')


def test_indiana_enrolled_act_pdf_is_accepted():
    item = next(t for t in TASKS if t['example_id'].endswith('741577743871'))
    url = 'https://iga.in.gov/pdf-documents/123/2024/house/bills/HB1047/HB1047.06.ENRS.pdf'
    assert find_primary_source_reward(item, {'url': url, 'confidence': 'verified'}).reward == 1.0
    # the introduced bill sits in the same folder and is an earlier version, so it is not accepted
    intro = 'https://iga.in.gov/pdf-documents/123/2024/house/bills/HB1047/HB1047.01.INTR.pdf'
    assert find_primary_source_reward(item, {'url': intro, 'confidence': 'verified'}).outcome == 'unlisted'


def _item(suffix):
    return next(t for t in TASKS if t['example_id'].endswith(suffix))


def test_israel_bots_task_is_strict_on_the_draft_law():
    item = _item('df4888af5bd0')
    memo = ('https://www.tazkirim.gov.il/s/legislativeworkactivity/a133Y00000K4M9uQAF/%D7%94%D7%A4%D7%A6%D7%94-'
            '%D7%9C%D7%94%D7%A2%D7%A8%D7%95%D7%AA-%D7%A6%D7%99%D7%91%D7%95%D7%A8?language=iw')
    assert find_primary_source_reward(item, {'url': memo, 'confidence': 'verified'}).reward == 1.0
    # the ministries' release, at its old address or where that now redirects, is the announcement, not the text
    for url in ('https://www.gov.il/he/pages/15062022_1', 'https://www.gov.il/en/departments/news/15062022_1'):
        assert find_primary_source_reward(item, {'url': url, 'confidence': 'likely'}).outcome == 'announcement_only', url


def test_kenya_report_in_the_communications_authority_repository_is_accepted():
    url = 'https://repository.ca.go.ke/items/aa797b83-9f3f-49a7-9305-c5288f0fba8f'
    item = _item('911c6905bb9f')
    assert find_primary_source_reward(item, {'url': url, 'confidence': 'verified'}).reward == 1.0
    assert item['reference']['canonical_url'] == url


def test_brazil_bill_as_first_printed_is_accepted():
    # the Câmara's certified first printing (avulso) of PL 6.237/2025: same text, with the referral order
    url = 'https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3104780&filename=Avulso+PL+6237/2025'
    assert find_primary_source_reward(_item('3979ac328815'), {'url': url, 'confidence': 'verified'}).reward == 1.0


def test_australian_speech_at_its_moved_address_is_accepted():
    url = 'https://www.minister.industry.gov.au/charlton/media/speech-australian-business-economists-conference'
    assert find_primary_source_reward(_item('494dde36c08d'), {'url': url, 'confidence': 'verified'}).reward == 1.0


def test_where_key_pages_now_redirect_is_accepted():
    # checked 2026-11-22: these key addresses now redirect (node ids to named pages, the Câmara's bill page to its
    # tracking sheet), or name the page their old address now carries as canonical
    moved = {
        '19872e77eb80': ['https://ised-isde.canada.ca/site/isde/fr/declaration-ministres-lindustrie-numerique-technologie-g7-2025',
                         'https://ised-isde.canada.ca/site/ised/en/g7-industry-digital-and-technology-ministers-meeting-2025'],
        '7b04673ccece': ['https://www.pm.gc.ca/en/news/backgrounders/2026/03/06/canada-japan-comprehensive-strategic-roadmap',
                         'https://www.pm.gc.ca/en/news/readouts/2026/03/06/prime-minister-carney-meets-prime-minister-japan-takaichi-sanae'],
        '86b041549175': ['https://www.pm.gc.ca/fr/nouvelles/declarations/2026/10/30/declaration-commune-canada-et-lunion-europeenne-batissent',
                         'https://www.eeas.europa.eu/eeas/historic-eu-canada-summit-builds-alliance-future_en'],
        '90fc73701544': ['https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2430325&fichaAmigavel=nao'],
    }
    for suffix, urls in moved.items():
        for url in urls:
            assert find_primary_source_reward(_item(suffix), {'url': url, 'confidence': 'verified'}).reward == 1.0, url


def test_canonical_urls_point_at_live_pages():
    # the old canonical addresses 404 (TRAI's press release, MDDI's old path) or only load with www. (CBN)
    assert _item('d9a61b63e004')['reference']['canonical_url'].endswith('/2024-09/Recommendation_12042024_0.pdf')
    assert '/newsroom/' in _item('864db2fad3b9')['reference']['canonical_url']
    assert _item('8240b50ff795')['reference']['canonical_url'].startswith('https://www.cbn.gov.ng/')


def test_nigeria_task_whose_source_was_deleted_is_replaced():
    # the NITDA speech's only official page (Voice of Nigeria) was deleted in 2026; replaced by a live Nigerian task
    assert not any(t['example_id'].endswith('615889ba2bb2') for t in TASKS)
    item = _item('d9c8ea6ddad1')
    assert item['strata']['jurisdiction'] == 'NG' and not item['strata']['strict']
    url = 'https://fmino.gov.ng/45th-national-council-charts-new-course-for-a-future-ready-credible-and-efficient-civil-service/'
    assert find_primary_source_reward(item, {'url': url, 'confidence': 'verified'}).reward == 1.0


def test_official_answers_from_the_v0_3_0_baselines_are_accepted():
    # each opened and confirmed on 22 November 2026 (Claude Code and Codex baselines on v0.3.0)
    found = {
        '7307095c7864': 'https://www.boletinoficial.gob.ar/detalleAviso/primera/311381/202407290',
        '44317a47ecb0': 'https://legislation.nysenate.gov/pdf/bills/2023/s7543b',
        'afbdf3b43b52': 'https://likms.assembly.go.kr/bill/billDetail.do?billId=PRC_M2M6U0V7T0U8S1T2R3Z4A0Y6Z9X5X3',
        '87e420c1be48': 'https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=2461452&filename=Avulso+PL+2807%2F2024',
        '86b041549175': 'https://data.consilium.europa.eu/doc/document/ST-15148-2026-INIT/en/pdf',
        'd0e75ad2509f': 'https://www.mofa.gov.ae/en/mediahub/news/2025/11/18/18-11-2025-uae-korea',
        '609f322c21d9': 'https://presidency.gov.za/president-appoints-commission-fourth-industrial-revolution',
        '7b04673ccece': 'https://www.mofa.go.jp/files/100990649.pdf',
        'bce5eeb3104c': 'https://hansard.parliament.uk/Lords/2025-05-12/debates/45252051-8C6C-4193-A53D-AC083E777D08/DataUseAndAccessBillHl',
        '19872e77eb80': 'https://ised-isde.canada.ca/site/ised/en/node/679',
        '3979ac328815': 'https://planalto.gov.br/ccivil_03/projetos/ato_2023_2026/2025/pl/pl-6237.htm',
        '741577743871': 'https://iga.in.gov/legislative/2024/bills/house/1047',
        'c580acab1c8f': 'https://www.resmigazete.gov.tr/eskiler/2025/12/20251225-13.pdf',   # Decree 192: the AI directorate
        'fc52044ee88e': 'https://ncc.gov.ng/sites/default/files/2026-02/Internet-Code-of-Practice-2026.pdf',
    }
    for suffix, url in found.items():
        assert find_primary_source_reward(_item(suffix), {'url': url, 'confidence': 'verified'}).reward == 1.0, suffix
    item = _item('87e420c1be48')   # the bill as filed, too
    url = 'https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=2452315'
    assert find_primary_source_reward(item, {'url': url, 'confidence': 'verified'}).reward == 1.0
    item = _item('afbdf3b43b52')   # the government legislation portal's page for the bill
    url = 'https://community.lawmaking.go.kr/gcom/nsmLmSts/out/2220174/detailRP'
    assert find_primary_source_reward(item, {'url': url, 'confidence': 'verified'}).reward == 1.0


def test_wrong_answers_from_the_baselines_still_score_nothing():
    wrong = {
        '911c6905bb9f': 'https://www.ict.go.ke/blockchain.pdf',                             # 404
        'd9a61b63e004': 'https://trai.gov.in/sites/default/files/Recommendation_12042024.pdf',  # 404
        '90fc73701544': 'https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3137291',  # another bill
        'dce3c01bf369': 'https://www.soumu.go.jp/main_content/001097704.pdf',               # a later meeting
        '44760fdc8744': 'https://g7.utoronto.ca/summit/2026evian/260617-digital-space.html',  # not official
    }
    for suffix, url in wrong.items():
        assert not find_primary_source_reward(_item(suffix), {'url': url, 'confidence': 'likely'}).correct, suffix


def test_el_salvador_supreme_court_legal_database_is_an_official_host():
    assert 'jurisprudencia.gob.sv' in _item('8d91b7870f31')['reference']['authoritative_hosts']
