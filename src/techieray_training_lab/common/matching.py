"""URL matching for answers that are web addresses.

Both the answer URL and each accepted fragment are first reduced to a canonical form (`canonical`):

  - no scheme, no leading 'www.', no '#anchor' (a '#/...' page route is kept as a path), no trailing '/', percent-escapes decoded, all lower case
    (`hansard.parliament.uk/Commons/...` and `.../commons/...` are the same page);
  - language markers removed: a path segment that is a language code (`/en/`, `/ms/`, `/zh-cn/`) and query
    parameters such as `lang=` or `hl=`, so the English and Malay versions of one release match;
  - tracking parameters removed (`utm_*`, `fbclid`, `gclid`, `mc_cid`..., and `ref=`/`source=` whose value is a domain),
    and parameters that only name the download on one site (`filename=` on camara.leg.br);
  - known address families for one document reduced to one form. Today that is US federal bills: every congress.gov
    bill tab (`/text`, `/all-info`), the congress.gov text file (`/118/bills/s9876/BILLS-118s9876is.htm`) and the
    govinfo package for the bill all reduce to `congress.gov/bill/118th-congress/senate-bill/9876`. A US Federal
    Register notice reduces to its document number, on federalregister.gov or govinfo.gov. A Swiss federal news item
    reduces to its ID, on any admin.ch site. An EU act on EUR-Lex reduces to its ELI, whether addressed by CELEX
    number (`legal-content/EN/TXT/?uri=CELEX:32024R1689`) or ELI (`eli/reg/2024/1689/oj`). A California bill's text,
    status, history and versions tabs on leginfo reduce to its main page (`billNavClient.xhtml?bill_id=...`).

A fragment then matches when the canonical URL starts with it and the next character is end-of-URL, '/', '?' or '#'.
So `congress.gov/bill/119th-congress/house-bill/45` matches `.../house-bill/45` and `.../house-bill/45/text` but not
`.../house-bill/4512`. A fragment with a query string also matches an answer on the same path whose query holds all of
the fragment's parameters, in any order and with others added: `law.go.kr/lsInfoP.do?lsiSeq=268543` matches
`...?lsiSeq=268543&efYd=20250122` but not `...?lsiSeq=2685430`. The host must be the same (`president.gov.il` is not `gov.il`), and a fragment can never match
inside another site's query string.

A URL that still does not match may be a correct page the key does not list (another official page for the same
development). The reward scores it 0 unless a grader is used.
"""
import re
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit

BOUNDARY_CHARS = ('/', '?', '#')
# only a scheme at the very start is the scheme: 'gov.ie/pdf/?file=https://assets.gov.ie/x.pdf' is a gov.ie page
_SCHEME = re.compile(r'^[a-z][a-z0-9+.-]*://', re.I)

# ISO 639-1 codes, with optional region or script (en-gb, zh-hans, pt_br)
_ISO639_1 = set("""aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv cy da de dv
dz ee el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu hy hz ia id ie ig ii ik io is it iu
ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln lo lt lu lv mg mh mi mk ml mn mr ms mt my na nb nd ne
ng nl nn no nr nv ny oc oj om or os pa pi pl ps pt qu rm rn ro ru rw sa sc sd se sg si sk sl sm sn so sq sr ss st su sv
sw ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi vo wa wo xh yi yo za zh zu""".split())
_LANG_SEGMENT = re.compile(r'^([a-z]{2})(?:[-_][a-z0-9]{2,4})?$')
_LANG_PARAMS = {'lang', 'language', 'hl', 'locale', 'lng', 'lan'}
# tracking parameters carry no meaning for the page: always dropped, and ref= or source= when the value is a domain
# (ref=eutechloop.com), never a real reference (ref=COM(2025)265)
_TRACKING = re.compile(r'^(utm_\w+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|_hs\w+|ocid)$')
_DOMAIN_VALUE = re.compile(r'^[a-z0-9-]+(\.[a-z0-9-]+)+$')


# parameters that only name the download on one site, never which document it is: the Câmara's file viewer serves
# one document per codteor, whatever filename= says (codteor=3063060&filename=PL%206237/2025)
_COSMETIC_PARAMS = {'camara.leg.br': {'filename'}}


def _keep_param(k, v, host=''):
    if k in _LANG_PARAMS or _TRACKING.match(k):
        return False
    if any(k in names for site, names in _COSMETIC_PARAMS.items() if host == site or host.endswith('.' + site)):
        return False
    return not (k in ('ref', 'source') and _DOMAIN_VALUE.match(v))

_BILL_TYPES = {'hr': 'house-bill', 's': 'senate-bill', 'hres': 'house-resolution', 'sres': 'senate-resolution',
               'hjres': 'house-joint-resolution', 'sjres': 'senate-joint-resolution',
               'hconres': 'house-concurrent-resolution', 'sconres': 'senate-concurrent-resolution'}
_CONGRESS_PAGE = re.compile(r'^congress\.gov/bill/(\d+)(?:st|nd|rd|th)-congress/([a-z-]+)/(\d+)(?=$|[/?#])')
_CONGRESS_FILE = re.compile(r'^congress\.gov/(\d+)/bills/([a-z]+?)(\d+)(?=$|[/?#])')
_ADMIN_CH_NEWS = re.compile(r'^(?:[a-z0-9-]+\.)*admin\.ch/newnsb/([a-z0-9]+)(?=$|[/?#])')
_FEDERAL_REGISTER = re.compile(r'^(?:federalregister\.gov/(?:documents/\d{4}/\d{2}/\d{2}|d)'
                               r'|govinfo\.gov/(?:content/pkg/fr-\d{4}-\d{2}-\d{2}/(?:pdf|html)|app/details/fr-\d{4}-\d{2}-\d{2}))'
                               r'/(\d{4}-\d{4,6})(?=$|[/?#.])')
# an EU act by CELEX number (legal-content/EN/TXT/?uri=CELEX:32024R1689) or ELI (eli/reg/2024/1689/oj); a
# corrigendum (32024R1689R(01)) is a different document. Language segments are already gone in canonical form.
_EURLEX_CELEX = re.compile(r'^eur-lex\.europa\.eu/legal-content/(?:txt|all|auto)(?:/(?:pdf|html))?/?\?(?:[^#]*&)?'
                           r'uri=celex(?:%3[aA]|:)3(\d{4})([rld])(\d{4})(?![0-9a-z(%])')
_EURLEX_ELI = re.compile(r'^eur-lex\.europa\.eu/eli/(reg|dir|dec)/(\d{4})/(\d+)(?=$|[/?#])')
_EU_KINDS = {'r': 'reg', 'l': 'dir', 'd': 'dec'}
# a California bill's tabs on leginfo, by bill_id (202520260ab723); its votes and committee analyses are other pages
_LEGINFO_CA_BILL = re.compile(r'^leginfo\.legislature\.ca\.gov/faces/bill(?:nav|text|status|history|versions)client\.xhtml'
                              r'\?(?:[^#]*&)?bill_id=([0-9a-z]+)(?=$|&)')
_GOVINFO_BILL = re.compile(r'^govinfo\.gov/(?:content/pkg|app/details)/bills-(\d+)([a-z]+?)(\d+)[a-z]*(?=$|[/?#.-])')


def _ordinal(n: int) -> str:
    suffix = 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def _us_bill(congress: str, kind: str, number: str):
    if kind not in _BILL_TYPES:
        return None
    return f'congress.gov/bill/{_ordinal(int(congress))}-congress/{_BILL_TYPES[kind]}/{int(number)}'


def _known_families(u: str) -> str:
    m = _ADMIN_CH_NEWS.match(u)
    if m:  # Swiss federal news items keep one ID across every admin.ch site (bsv.admin.ch, admin.ch, ...)
        return f'admin.ch/newnsb/{m[1]}'
    m = _FEDERAL_REGISTER.match(u)
    if m:  # one Federal Register document number, on federalregister.gov or govinfo.gov
        return f'federalregister.gov/d/{m[1]}'
    m = _EURLEX_CELEX.match(u)
    if m:  # every EUR-Lex address of one act reduces to its ELI
        return f'eur-lex.europa.eu/eli/{_EU_KINDS[m[2]]}/{m[1]}/{int(m[3])}'
    m = _EURLEX_ELI.match(u)
    if m:
        return f'eur-lex.europa.eu/eli/{m[1]}/{m[2]}/{int(m[3])}'
    m = _LEGINFO_CA_BILL.match(u)
    if m:  # every tab of one California bill reduces to its main bill page
        return f'leginfo.legislature.ca.gov/faces/billnavclient.xhtml?bill_id={m[1]}'
    m = _CONGRESS_PAGE.match(u)
    if m:
        return f'congress.gov/bill/{_ordinal(int(m[1]))}-congress/{m[2]}/{int(m[3])}'
    for pattern in (_CONGRESS_FILE, _GOVINFO_BILL):
        m = pattern.match(u)
        if m and (bill := _us_bill(*m.groups())):
            return bill
    return u


def _is_language(segment: str) -> bool:
    m = _LANG_SEGMENT.match(segment)
    return bool(m) and m[1] in _ISO639_1


def _drop_anchor(url: str) -> str:
    """Drop a '#anchor', but keep a '#/...' route: single-page sites (Singapore's Hansard) identify pages that way."""
    url = (url or '').strip().replace('/#/', '/').replace('#/', '/')
    return url.split('#', 1)[0]


def canonical(url: str) -> str:
    """The comparable form of a URL or fragment (see the module docstring)."""
    u = _SCHEME.sub('', _drop_anchor(url))
    u = unquote(u).lower()
    if u.startswith('www.'):
        u = u[4:]
    path, _, query = u.partition('?')
    host, _, rest = path.partition('/')
    segments = [s for s in rest.split('/') if s and not _is_language(s)]
    path = '/'.join([host.rstrip('.')] + segments)
    # fragments drop a trailing '/', which can belong to the last query value (contextPath=/viewer/)
    params = [(k, v.rstrip('/')) for k, v in parse_qsl(query, keep_blank_values=True) if _keep_param(k, v, host)]
    u = path + ('?' + urlencode(params) if params else '')
    return _known_families(u)


def url_matches(url: str, fragment: str) -> bool:
    if not url or not fragment:
        return False
    u, f = canonical(url), canonical(fragment)
    if not f:
        return False
    if u.startswith(f) and (len(u) == len(f) or u[len(f)] in BOUNDARY_CHARS):
        return True
    f_path, _, f_query = f.partition('?')
    u_path, _, u_query = u.partition('?')
    if not f_query or u_path != f_path:
        return False
    u_params = parse_qsl(u_query, keep_blank_values=True)
    return all(param in u_params for param in parse_qsl(f_query, keep_blank_values=True))


def same_page(a: str, b: str) -> bool:
    """True when two URLs have the same canonical form."""
    return bool(a) and bool(b) and canonical(a) == canonical(b)


def fragment_for(url: str) -> str:
    """The accepted-answer fragment for a reference URL: no scheme, no leading 'www.', no '#anchor', no trailing '/'.

    `https://www.elysee.fr/en/x/` becomes `elysee.fr/en/x`. The fragment keeps the URL's own spelling so a reader can
    open it; matching canonicalises both sides.
    """
    url = _SCHEME.sub('', _drop_anchor(url))
    if url.startswith('www.'):
        url = url[4:]
    return url.rstrip('/')


def host(url: str) -> str:
    try:
        h = (urlsplit((url or '').strip()).hostname or '').lower()
    except ValueError:
        return ''
    return h[4:] if h.startswith('www.') else h
