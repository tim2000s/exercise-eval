# Nightscout from a browser-only client

Reference for `js/nightscout.js`. Claims marked with a file path were read from the
cgm-remote-monitor source at v15.0.7; claims marked AAPS were read from the AndroidAPS
Nightscout SDK at master. Where something was inferred rather than verified, the text says so.

## 1. The one thing a user has to change

A stock Nightscout site sends no `Access-Control-Allow-Origin` header, so a fetch from
`https://tim2000s.github.io` fails in the browser before the response body can be read. The
site owner adds one word to an existing environment variable:

```
ENABLE=<whatever is already there> cors
CORS_ALLOW_ORIGIN=*
```

`cors` is absent from every deployment template in the repository: the Heroku button
(`app.json:112`), the Azure ARM template (`azuredeploy.json:176`), the Docker Compose file
(`docker-compose.yml:57`) and the sample env file (`docs/example-template.env:6`). The AAPS
setup guide's suggested list omits it too. Only the Nightscout documentation's own example
includes it. Assume the user has to add it.

`CORS_ALLOW_ORIGIN` does nothing on its own. The mapping from environment variable to
`extendedSettings.cors.allowOrigin` runs in `findExtendedSettings` (`lib/server/env.js:213-244`),
which iterates over the enabled plugin list and only looks for variables prefixed with the name
of a plugin that is enabled. Setting the origin without enabling `cors` fails silently.

`CORS_ALLOW_ORIGIN=https://tim2000s.github.io` also works and is tighter. It has two costs. A
GitHub Pages custom domain changes the origin and breaks it, and Nightscout emits no
`Vary: Origin`, so a site behind Cloudflare can cache a response carrying an origin-specific
header and serve it to a different origin. On balance `*` is the better advice here, because
without `Access-Control-Allow-Credentials` (which Nightscout never sends) a wildcard exposes
only what is already anonymously readable.

The user can check the change took effect without opening a browser:

```bash
curl -s -D- -o /dev/null -H 'Origin: https://tim2000s.github.io' \
  'https://<site>/api/v1/status.json' | grep -i access-control
```

Silence means `cors` is not in `ENABLE`, or the service was not restarted. The server also logs
`Enabled CORS, allow-origin: <value>` at startup (`lib/server/app.js:167`).

## 2. Authentication, and why the api-secret header cannot be used

The CORS middleware is fifteen lines (`lib/server/app.js:165-179`) and the header list it
allows is fixed:

```
Access-Control-Allow-Headers: Content-Type, Authorization, Content-Length, X-Requested-With
```

`api-secret` is not in that list. A request carrying it triggers a preflight, the preflight is
answered 200 with the list above, and the browser then aborts the real request. This was
reproduced against express 4.17.1, the version Nightscout pins, and is reported upstream as
cgm-remote-monitor issue 6981 with the exact browser message. The issue is closed with no fix
and the header list at v15.0.7 is unchanged.

What works instead, in order of preference:

1. No credential at all. `AUTH_DEFAULT_ROLES` defaults to `readable` (`lib/settings.js:40`), the
   `readable` role carries `*:*:read` (`lib/authorization/storage.js:141`), and
   `GET /api/v1/entries.json` requires `api:entries:read` (`lib/api/entries/index.js:57`). On a
   default site, reads need nothing. A plain `fetch(url)` with no author-set headers is a simple
   request, so no preflight is issued.
2. `?token=<subject-token>` in the query string (`lib/authorization/index.js:46`), for a site
   running `AUTH_DEFAULT_ROLES=denied`. A subject token carries a role rather than
   administrative rights, so a read-only token is the right thing to paste into a browser tool.
   Still a simple request, still no preflight.
3. `?secret=<api secret>` (`lib/authorization/index.js:82`) works and is checked before the
   header, but it is the full administrative secret and should not be used here.

The client sends `credentials: 'omit'`, because Nightscout never sends
`Access-Control-Allow-Credentials` and a credentialed request would fail regardless.

API v3 is not used. `lib/api3/security.js:28-40` accepts only a `Authorization: Bearer` header
and rejects everything else with 401, so every v3 request from a browser costs a preflight, and
the JWT has to be fetched first from `/api/v2/authorization/request/<token>`. API v1 with a
query-string token is simpler and is what every deployment supports.

## 3. The implicit four-day window

This is the trap most likely to produce a tool that silently shows only recent data.
`lib/server/query.js:81-88`: when a query carries neither a date constraint nor `dateString`,
the server injects `$gte: now - deltaAgo`, where `deltaAgo` defaults to 345,600,000 ms, that is
four days (`lib/server/query.js:35`). So `entries.json?count=25000` returns four days of data
no matter how large the count, with no error and no indication that a limit was applied.

The date field differs by collection:

| Collection | Field | Representation |
|---|---|---|
| entries | `date` | epoch milliseconds (`lib/server/entries.js:180`, `useEpoch: true`) |
| treatments | `created_at` | ISO 8601 string (`lib/server/treatments.js:246`) |
| devicestatus | `created_at` | ISO 8601 string |

Default counts also differ: entries default to 10, treatments to 1000 when a `find` is present
and 100 when it is not (`lib/api/treatments/index.js:87`). The client always passes `count`
explicitly and always passes a date filter.

## 4. Fetching a long history

Nightscout applies no rate limiting of any kind. Grepping the source for `rate-limit`,
`throttle`, `429` and `Too Many Requests` returns nothing, and no rate-limiting package appears
in its dependencies. There is no server-side cap on `count` either: `lib/server/entries.js:33-36`
passes `parseInt(opts.count)` straight into Mongo's `.limit()`.

The constraints that do exist are elsewhere. Platform request timeouts bound a single large
query: Heroku 30 s, Fly.io about 30 s (community reports rather than documentation), Railway
five minutes with no data transferred. The MongoDB Atlas M0 free tier that most self-managed
sites use has 512 MB of storage and no performance guarantee, and Nightscout's own
documentation notes that frequent polling loads it.

Response size, estimated from representative documents rather than measured: 250 to 350 bytes
per entry uncompressed, so roughly 7 MiB for 25,000 entries, which is about 87 days at
five-minute resolution. Responses are gzipped (`lib/server/app.js:187-194`) and entry documents
compress better than 10:1, so that travels as under 1 MiB. The cost is server memory rather
than bandwidth, since the whole result set is materialised in the Node process first.

The client therefore pages backwards in windows of seven days using `find[date][$lt]` on the
oldest timestamp seen, with a short delay between pages. That keeps every request well inside
any platform timeout, makes the fetch resumable, allows a progress bar, and is neighbourly to a
shared Atlas instance.

There is an in-process cache that serves reads without touching MongoDB when `count` is small
enough and the only `find` key is `type` (`lib/api/entries/index.js:493`). It holds two days of
entries, 60 hours of treatments and one day of devicestatus (`lib/server/cache.js:26-31`).
Queries that fit are effectively free. A historical backfill will not fit and every request
reaches the database.

`eventType` and `notes` on treatments accept a regex: `parseRegEx`
(`lib/server/query.js:250-256`) converts a `/pattern/flags` string to a `RegExp` and otherwise
matches exactly. So `find[eventType]=/^Temp/i` works, which is how the client pulls only the
treatment kinds it needs.

## 5. Treatment event types as AAPS actually writes them

The care portal list (`lib/plugins/careportal.js:11-107`) is what a human clicking the web
interface produces. AAPS writes a different and narrower set, and the mapping is not what the
names suggest.

Boluses, from `BolusExtension.kt:28`:

```kotlin
eventType = if (type == BS.Type.SMB) EventType.CORRECTION_BOLUS else EventType.MEAL_BOLUS
```

Every SMB is `Correction Bolus`. Every other bolus, including a correction the person dialled by
hand, is `Meal Bolus`. AAPS never writes `Snack Bolus`.

Carbohydrate, from `CarbsExtension.kt:26`:

```kotlin
eventType = if (amount < 12) EventType.CARBS_CORRECTION else EventType.MEAL_BOLUS
```

Carbs below 12 g are `Carb Correction`, and 12 g or more are `Meal Bolus` with no insulin field.
So `Meal Bolus` documents from AAPS are a mixture of insulin-only, carbs-only and both, and the
parser must not assume an `insulin` field is present.

An SMB is identified as `eventType === 'Correction Bolus' && (isSMB === true || type === 'SMB')`.
Current AAPS writes both fields; older documents carry only one.

`Bolus Wizard` is a separate record uploaded alongside the bolus, carrying
`bolusCalculatorResult` as a JSON string, not a replacement for it.

Temp basals are `Temp Basal`, written by `TemporaryBasalExtension.kt`. `rate` is always present
and always absolute U/h. `absolute` appears only for absolute-rate temp basals and `percent`
only for percentage ones, where `percent` is the delta from 100, so a 60 percent temp basal
writes `percent: -40`. The client reads `rate` and ignores the others.

A temp basal that ends early is not a second document. AAPS amends the original record in place
with a shortened `duration` and an `endId`. The treatments collection is therefore not
append-only for temp basals and a cached copy can go stale, which is why the client refetches
rather than appending. `Temp Basal End` exists in the care portal for humans; AAPS does not use
it. Both `Temp Basal` and the `Temp Basal Start` / `Temp Basal End` pair occur in the wild.
`Temporary Basal` is not used anywhere and is not matched.

Effective Profile Switch arrives as `eventType: 'Note'`. There is no
`Effective Profile Switch` string on the wire. `EffectiveProfileSwitchExtension.kt:40` sets the
event type to NOTE and the decoder discriminates on `eventType === 'Note' && originalProfileName != null`
(`TreatmentMapper.kt:197`). A client that renders notes will otherwise show these as blank
comments.

`Profile Switch`, with a space, carries `profile` (the name), `percentage` (100 when
unmodified), `timeshift` (lower-case on the wire, `timeShift` in Kotlin), `duration` in minutes
alongside `durationInMilliseconds`, and `profileJson`. `profileJson` is the whole profile as a
JSON string, not a nested object, so it must be parsed. It contains `units`, `dia`, `timezone`
and the `sens`, `carbratio`, `basal`, `target_low` and `target_high` arrays.

## 6. Temporary targets, and how exercise is actually recorded

`eventType: 'Temporary Target'`. AAPS always sends `targetTop` and `targetBottom` in mg/dL with
`units: 'mg/dl'` hard-coded, whatever the display units.

The `reason` field is a closed enum of six values in AAPS (`TT.kt:36-42`): `Custom`, `Hypo`,
`Activity`, `Eating Soon`, `Automation`, `Wear`. Unrecognised strings fall back to `Custom`.
Nightscout's own care portal offers a shorter list (`lib/plugins/openaps.js:287-296`):
`Eating Soon`, `Activity`, `Manual`. So `Manual` and `Custom` mean the same thing from different
origins.

`Exercise` is an event type, not a temp target reason. The temp target reason for exercise is
`Activity`.

A cancelled temp target is a `Temporary Target` document with `duration: 0`, not a
`Temporary Target Cancel`; that string exists only in the UI and is rewritten on submit
(`lib/client/careportal.js:323-326`). A cancel may legitimately carry no target fields at all
(`TreatmentMapper.kt:88-110`), so the parser must not require them.

Three routes record exercise, and the tool reads all three:

| Route | Document | Strength as a signal |
|---|---|---|
| Temp target with `reason: 'Activity'` | `Temporary Target`, `duration`, `targetTop`/`targetBottom` | Strongest. It is the thing that actually changed the loop's behaviour, and it is what most people do |
| Care portal exercise event | `Exercise`, `duration` in minutes, `notes` | Corroborating. Records intent but changes nothing |
| Reduced profile percentage | `Profile Switch` with `percentage` below 100 and a `duration` | Weakest, since a profile switch has other uses |

Treating the temp target as primary is a judgement about how people use AAPS, not a documented
convention, and the tool labels a session's insulin action by which of the three it found.

## 7. Autosens

The autosens ratio reaches Nightscout inside devicestatus, at
`devicestatus[].openaps.suggested.sensitivityRatio` and the matching `enacted` path.
`DeviceStatusExtension.kt:15-16` copies the algorithm result verbatim, and Nightscout reads it
from the suggested side only (`lib/plugins/openaps.js:402`).

One caveat matters for this tool in particular. `sensitivityRatio` is not always the autosens
ratio. When a temp target is active and temp-target sensitivity adjustment is enabled, the ratio
is derived from the target instead and the autosens value is discarded
(`DetermineBasalSMB.kt:238-247`). Under an exercise temp target, which is the exact situation
this tool analyses, a ratio well below 1 reflects the raised target rather than the person's
insulin sensitivity. Reading it as sensitivity there would be wrong, so the analysis ignores
`sensitivityRatio` for any interval covered by an active temp target and says so in the report.

`variable_sens` carries the dynamic ISF value when dynamic ISF is running.

Treatments record what the pump did; `devicestatus.openaps.enacted` records what the algorithm
decided on each five-minute cycle. They diverge when a command failed or the pump was out of
range. Insulin accounting uses treatments, and algorithm behaviour uses devicestatus.

## 8. Request shapes used by the client

```js
// Status, to detect units and confirm CORS in one call.
fetch(`${base}/api/v1/status.json`, { credentials: 'omit' })

// CGM entries, one seven-day page, newest first.
fetch(`${base}/api/v1/entries.json?count=2500`
    + `&find[date][$gte]=${windowStartMs}&find[date][$lt]=${windowEndMs}`,
      { credentials: 'omit' })

// Treatments over the same window. created_at is an ISO string here, not epoch millis.
fetch(`${base}/api/v1/treatments.json?count=5000`
    + `&find[created_at][$gte]=${new Date(windowStartMs).toISOString()}`
    + `&find[created_at][$lt]=${new Date(windowEndMs).toISOString()}`,
      { credentials: 'omit' })

// Profile, for basal schedule, ISF, carb ratio and DIA.
fetch(`${base}/api/v1/profile.json`, { credentials: 'omit' })
```

A read-only token, where the site needs one, is appended as `&token=<name-hash>`.

## 9. Units

`status.json` reports the site's display units under `settings.units`, as `mg/dl` or `mmol`.
Entries always store `sgv` in mg/dL regardless, and AAPS always writes temp target bounds in
mg/dL. The client converts once at the boundary and works in mmol/L internally, since that is
what the user reads. The conversion factor is 18.0182 mg/dL per mmol/L.

## 10. Known failure modes worth surfacing to the user

| Symptom | Cause | Fix |
|---|---|---|
| Fetch fails immediately, console shows a CORS error | `cors` not in `ENABLE` | Add it and restart the service |
| Two `Access-Control-Allow-Origin` headers, browser rejects | CORS set both in Nightscout and at a reverse proxy | Pick one owner of the header |
| Works from one browser, fails from another on the same site | Cloudflare cached a response carrying an origin-specific header | Use `CORS_ALLOW_ORIGIN=*` |
| Only the last four days appear despite a large count | No date filter, so the implicit window applied | Pass `find[date][$gte]` |
| 401 on every request | `AUTH_DEFAULT_ROLES=denied` | Create a read-only subject token and paste it |
| Long fetch dies partway | Platform request timeout | The client pages in seven-day windows, so this should not occur |
