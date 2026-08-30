# Exercise evaluation for type 1 diabetes

A browser page that reads a Nightscout site and an activity file, then compares what happened
around each exercise session against the published guidance on exercise in type 1 diabetes.
Everything runs in the browser. No data is uploaded, and there is no server to upload it to.

**This is not medical advice.** It reads a record after the event and compares it against
population-level guidance, without knowing anyone's history, insulin sensitivity, what else was
happening that day, or what their clinical team has told them. Much of the guidance it quotes is
expert consensus rather than trial evidence, and each finding says which it is. Any change to
insulin or food belongs with the team who look after the person's diabetes.

## What it does

For each exercise session it finds, the tool reports three things separately, because they carry
different weight:

- What the record shows. Glucose at the start, the nadir, the change, time below range, what
  insulin and carbohydrate were given and when, and how hard the session was from heart rate.
- What the published guidance says about that, with the citation, the study design and the
  number of participants behind it.
- What to change, which is an inference from both that a reader is entitled to disagree with.

It then looks across sessions of the same kind for a pattern, and says plainly when there are
too few to describe one.

## Choosing what to look at

A date range governs both what is fetched from Nightscout and which sessions are offered, and
the sessions inside it are then listed individually so specific ones can be picked. That matters
more than it sounds: ninety days produces a report nobody reads, while three sessions you were
actually curious about produce one you will.

Sessions are grouped by day and show duration, distance, whether heart rate was recorded, and
which app wrote them. Any that fall outside the glucose data fetched are listed but not
selectable, since evaluating one would produce a page of findings that all say the same thing
about missing data.

A day either side of the chosen range is fetched as well. The analysis needs it: time below
range in the 24 hours before a session predicts post-exercise nocturnal hypoglycaemia about as
strongly as the exercise does, and the delayed risk period runs 7 to 11 hours afterwards, which
for an evening session falls in the night that follows.

## Getting it working

### Nightscout

A browser will not let one website read another unless the second one says it may. A stock
Nightscout sends no such header, so the fetch fails before any data is read. The site owner adds
one word to a variable they already have:

```
ENABLE=<whatever is already there> cors
CORS_ALLOW_ORIGIN=*
```

Then restart the service. Setting `CORS_ALLOW_ORIGIN` without adding `cors` to `ENABLE` does
nothing, and does so silently, which is the usual reason a second attempt fails the same way as
the first. To check it took effect without opening a browser:

```bash
curl -s -D- -o /dev/null -H 'Origin: https://tim2000s.github.io' \
  'https://<your-site>/api/v1/status.json' | grep -i access-control
```

Most Nightscout sites allow anonymous reads, so no token is needed. Where one is, create a
read-only subject token in Admin Tools. The API secret cannot be used from a browser at all: it
is absent from Nightscout's fixed `Access-Control-Allow-Headers` list, so the preflight succeeds
and the browser then aborts the real request.

### Activity data

The tool sniffs the file's bytes rather than trusting its name, and accepts:

| Source | What to give it |
|---|---|
| Health Connect | The scheduled export zip. There is no on-demand export: set up a daily, weekly or monthly schedule in Health Connect, then collect the file from wherever it was written |
| Strava | Either the bulk export archive, or a direct connection (below) |
| Garmin Connect | The account export, or a single activity file |
| Anything else | Individual FIT, TCX, GPX, CSV or JSON files |

### Connecting to Strava directly

This works from a static page, which is not obvious in advance: Strava sends
`Access-Control-Allow-Origin: *` on both its API and its token endpoint, so the whole
authorisation flow runs in the browser with nothing in between.

What it costs you is a Strava application of your own. Strava has no public-client mode and no
PKCE, so the token exchange needs a client secret, and there is no arrangement in which a shared
one could be held safely in a public page. Registering an application at
[strava.com/settings/api](https://www.strava.com/settings/api) takes a few minutes, requires a
paid Strava subscription, and gives you a client ID and secret to paste in. Set the
authorisation callback domain to the domain the page is served from, with no scheme and no path.

Both values stay in your browser and are sent only to Strava. Disconnect and forget removes
them; revoking the application on Strava ends its access regardless.

Activities fetched this way are held in memory for the visit and never written to storage. Heart
rate detail is a separate request per activity against a budget of 100 requests every fifteen
minutes, so it is fetched only for the sessions you choose to analyse. Sessions without it still
carry the average and maximum heart rate from the summary, which fixes how hard a session was on
average and says nothing about whether it was steady or intervals; the report marks that
distinction rather than papering over it.

One thing to weigh. Strava's API policy of June 2026 caps retention of their data at seven days
and, read strictly, restricts processing it for analysis at all, while the same document
explicitly protects your right to export your own data through their bulk export tool. Nothing
here is stored and the analysis runs on your own machine, but the export route sits outside
those terms entirely. `docs/strava-api.md` sets out the clauses and what the tool does about
them.

More than one file can be added. A session that appears in two files is kept once, keeping
whichever copy carried heart rate.

The Health Connect export is not encrypted, despite a claim to the contrary that circulates
widely and appears in a stale comment on the Android class itself. It holds one plain SQLite
database, which is why this page can read it. It also retains GPS route data at full precision.
Nothing leaves the browser here, but that is worth knowing before sharing the file elsewhere.

Apple Health exports are not supported. They are a single flat XML document commonly 200 to
500 MB unzipped, which a browser cannot parse as a document. Exporting individual workouts as
GPX, TCX or FIT gives the tool something it can read.

## How it is put together

```
index.html            the page
css/style.css         theme-aware styling, light and dark both explicitly defined
js/
  app.js              wiring, and nothing that decides anything about diabetes
  nightscout.js       the Nightscout client
  import.js           file type detection and dispatch
  charts.js           inline SVG, two plots on a shared time axis
  pyodide-bridge.js   loads the Python engine, lazily
  parsers/            one module per format
python/xeval/
  sources.py          the bibliography, with design, participants and population
  guidelines.py       the published numbers, each pointing at a source
  intensity.py        what heart rate says about how hard a session was
  insulin.py          insulin on board, and what was done to basal and bolus
  evaluate.py         what happened to glucose, measured rather than assumed
  recommend.py        the rules, which contain no numbers of their own
  report.py           assembly, and the cross-session summary
docs/                 the literature this is built on, with every figure sourced
```

The analysis is written in Python and runs in the browser under Pyodide. It is served as
readable files under `python/xeval/`, so any number in a report can be traced back to the code
that produced it and to the paper that produced that. The same code runs unmodified under
CPython, which is what the test suite exercises.

`recommend.py` holds no numbers. Every figure it quotes comes from `guidelines.py`, and every
entry there names a source in `sources.py` that records the study design, the number of
participants and the population. That separation matters more here than it usually would.
Almost all of the pre-exercise threshold material is graded D, meaning expert opinion, and the
20 percent overnight basal reduction that every guideline gives rests on two trials totalling 26
people. Where guidelines disagree, both figures are held and the disagreement is reported rather
than resolved silently.

## Some things the literature says that the tool is built around

A reduced meal bolus does not slow the fall in glucose during exercise. In every arm of the
trial the reduction table comes from, the fall was the same size on a reduced dose as on a full
one. What changed was that glucose was higher when exercise began, so the same fall landed
somewhere safer.

Lead time on a basal reduction is not a refinement, it is the mechanism. Halving a basal rate an
hour before exercise removes about 5 percent of circulating insulin by the time exercise starts,
and the fall does not reach significance until 75 minutes.

Announcing exercise to a closed loop helps when a meal bolus is still active and has not been
shown to help when it is not. Two randomised trials found a large benefit with exercise 90
minutes after a meal; two found none at least three hours after the last bolus, and one measured
a cost in time in range.

Time below range in the preceding 24 hours predicts post-exercise nocturnal hypoglycaemia about
as strongly as the exercise itself, and it is measurable from CGM alone.

A rate of fall can be stated with an interval but not with a point a person should act on. The
pooled figure for continuous moderate work is -4.4 mmol/L per hour with a 95 percent confidence
interval of -6.1 to -2.8, and the intraclass correlation for the same person repeating the same
session is 0.12.

Each of these is set out with its source in `docs/`.

## Running the tests

```bash
npm install          # development only; the published site has no npm dependency
npm test             # the JavaScript parsers and the Nightscout client
python3 -m pytest tests/ -q      # the analysis engine
python3 tools/mutation_check.py  # checks that those tests can actually fail
./tools/browser_check.sh         # the real module graph and the real page, in headless Chrome
python3 tools/verify_deployment.py  # that the published site is the code all of the above ran on
```

The mutation check is there because a test that cannot fail is worse than no test. It breaks the
implementation in 32 specific ways, each a plausible defect, and reports any that no test
catches. The browser check covers what the others cannot: that the module graph resolves, that
the vendored SQLite and zip libraries work, that the charts produce valid SVG, that the page
itself loads and wires up, and that the Python engine loads under Pyodide and reaches the same
answer it reaches under CPython.

The browser check runs against a local copy rather than the published site, because Chrome's
Private Network Access rules stop a page served from a public origin from reporting back to a
harness on localhost. `verify_deployment.py` closes that gap from the other direction, by
comparing every published file against the working tree the checks ran on.

Test fixtures are generated rather than committed as opaque binaries:

```bash
python3 tools/make_fixture.py      # a synthetic Health Connect export
python3 tools/make_fit_fixture.py  # a valid FIT activity file
```

## Language

Person-first throughout, following the NHS Language Matters guidance: a person with type 1
diabetes rather than a diabetic, and no use of control, compliance or failure to describe anyone
or their glucose.

## Licence

MIT. See `LICENCE`.
