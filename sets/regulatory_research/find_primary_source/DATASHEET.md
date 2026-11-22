# Datasheet

This datasheet describes the 50 tasks in `data/tasks.jsonl`. 45 have an official source and 5 do not.

## Why the tasks exist

Legal and compliance professionals rely on primary sources, not on news coverage. AI research agents are increasingly
asked to find those sources, and they often return a news story, a law firm's summary or the wrong government page.
These tasks train and test one skill. Given news of a legal or regulatory development, the agent finds the official
document behind it.

## Where the tasks come from

Every task starts from an entry in the Global AI Regulation Tracker (techieray.com). The tracker's editor, a lawyer,
records each development with a link to its official source. That link is the starting point for the answer key.

Each task with a source then went through these steps.

1. **The answer key was checked.** The editor confirmed that the key is the official source for the development.
2. **Every official answer was collected.** Besides the tracker's link, the key lists other official pages for the
   same development where they exist, such as the document itself, the issuing body's announcement, co-issuers'
   releases and official copies in other languages. Each page was opened and checked before it was added. Most tasks
   with a source accept two or more pages, and one accepts eleven.
3. **Laws and bills were made strict where possible.** For 19 tasks the key is the authoritative text on an official
   register, such as a legislature's bill system, an official gazette or a national legislation database. On those
   tasks an announcement about the instrument does not count. Candidate texts were found through official sources
   such as govinfo, the Federal Register, EUR-Lex records and parliamentary bill systems, then confirmed.
4. **The question was rewritten.** The tracker's headline usually names the law, which makes the task trivial. Each
   headline was rewritten as a short news alert, with model assistance, that keeps what happened, where and roughly
   when, but drops titles, bill and citation numbers, names of people and named bodies, and exact figures. An
   automatic check rejected any alert that still gave the document away, and the editor checked the results.
5. **Problems were fixed or removed.** Duplicate tasks about the same instrument were reduced to one. Tasks with a
   homepage as the answer, a news site as the answer or no live official source were removed. Mislabelled
   instrument types and jurisdictions were corrected.

### The no-source tasks

Five tasks are deliberate traps. Each takes a real development and moves it to a jurisdiction where it did not
happen, for example a law from one US state restated as passed in another. The alert was written in the same style as
the others. Each trap then passed two independent web checks, the second in the jurisdiction's own language and its
own official sources, and neither found an official document for it. The editor then approved each one. The right
answer is that no official source exists, and citing the real development's page is wrong.

None of these tasks appears in techieray's held-out evaluation set or its free benchmark sample.

## What the tasks cover

**Regions** Africa 8, Asia-Pacific 8, Europe 8, North America 8, Latin America and Caribbean 7, Middle East 6,
International 5. The tasks cover 29 jurisdictions, five of them international bodies, and US tasks are capped at
about 15%.

**Instrument types**

| Type | Tasks |
|---|---|
| Binding law | 12 |
| Bill | 9 |
| Agreement | 6 |
| Declaration | 6 |
| Strategy | 5 |
| Guidance | 3 |
| Enforcement action | 3 |
| Other | 3 |
| Executive order | 2 |
| Treaty | 1 |

**Areas of law** Privacy 15, public sector 9, AI-specific law 4, online safety 4, cybersecurity 4, national security
3, human rights 3, consumer 2, intellectual property 2, trade 2, health 1, competition 1. The types and areas of the
no-source tasks are those of the real development each was made from.

**Answer pages** For the 45 tasks with a source, the main answer is HTML for 37 and PDF for 8. 15 are in a language
other than English, among them Portuguese, Spanish, Chinese, Korean, Turkish, Hebrew, Arabic and Italian.

**Dates** The developments run from March 2024 to November 2026. 13 tasks have no date, because the tracker records
some laws as standing entries rather than dated news.

## Fields

| Field | What it holds |
|---|---|
| `example_id` | A stable identifier |
| `input` | The question given to the agent, which is the vague alert with its jurisdictions and date |
| `input_named` | The same question with the tracker's own headline, an easier form |
| `input_full` | The tracker headline plus a short description, the easiest form |
| `reference.accepted_url_fragments` | The pages that count as correct, compared after normalisation. Empty on no-source tasks |
| `reference.no_official_source` | True on the five no-source tasks |
| `reference.authoritative_url_fragments` | On strict tasks, the only pages that score |
| `reference.authoritative_hosts` | On strict tasks, the official sites where a grader may accept another copy of the text |
| `reference.canonical_url` | One correct answer, as a full URL |
| `strata` | Tags for analysis, such as region, jurisdiction, area of law, instrument type, format, language and whether the task is strict |

## Known limits

- **Other correct pages may exist.** The keys list every official page that could be opened and checked, but some
  government sites block automated access, and a correct page on one of them may be missing. Without a grader, an
  unlisted but correct page scores 0. This is never penalised, but it adds noise, which the optional grader removes.
- **A no-source task could turn out to be true.** Two independent searches found nothing for each trap, but a
  development can be missed or can happen later. If one is found, it will be corrected in a later release.
- **Links can move.** Government sites restructure. The keys were live when checked, and pages under a key and known
  alternative addresses still match, but some links will break over time.
- **Dates are news dates.** A task's date is when the development was reported. The official text sometimes appeared
  later, for example when an act was published in an official journal after its adoption.
- **Language tags are automatic.** `source_language_guess` was set automatically and may be wrong for pages that mix
  languages.
- **Fifty tasks is a sample.** It shows the format and quality of the full set. It is too small to measure an agent
  precisely.
