# Strava from a browser with no server

Reference for `js/strava.js`. The CORS behaviour below was measured against the live endpoints
on 30 August 2026 rather than taken from documentation, because the documentation does not say.

## 1. It works, and that is not obvious

Strava sends `Access-Control-Allow-Origin: *` on the data endpoints and on the token endpoint,
and its preflight response explicitly allows the `authorization` header. So a static page can
complete the whole authorisation code exchange and read the API afterwards, with nothing in
between.

```
OPTIONS /api/v3/athlete
Origin: https://tim2000s.github.io
Access-Control-Request-Method: GET
Access-Control-Request-Headers: authorization

HTTP/2 200
access-control-allow-origin: *
access-control-allow-headers: authorization
access-control-allow-methods: GET, POST, PUT, DELETE
access-control-max-age: 600
```

The token endpoint answers a preflight for `POST` with `content-type` the same way. In practice
the client sends `application/x-www-form-urlencoded`, which is a CORS-safelisted content type,
so no preflight is issued for the exchange at all.

The strongest corroboration is Strava's own: `developers.strava.com/playground/` is a static HTML
page running Swagger UI, which performs the token exchange and every subsequent call in the
browser. Whatever else is true, browser-side access is not something Strava has engineered
against.

## 2. The three things that constrain the design

### No PKCE, so a client secret is unavoidable

Posting a token request with `code_verifier` and no `client_secret` is rejected on the missing
secret before anything else is looked at. `response_type=token` is rejected at the authorisation
endpoint, so there is no implicit flow either. There is no public-client mode of any kind.

This rules out a shared application. Shipping one client secret inside a public page would
publish it to everyone who views source. Each person therefore registers their own Strava
application and supplies their own credentials, which is the arrangement Strava calls Single
Player Mode. It costs the user a few minutes once, and it requires a paid Strava subscription,
which is a hard gate rather than an inconvenience.

### The rate limit headers cannot be read

Strava returns `X-RateLimit-Usage` and `X-ReadRateLimit-Usage` on every authenticated response,
and sends no `Access-Control-Expose-Headers`, so browser JavaScript is not permitted to read
any of them. An earlier version of this client parsed those headers and would have found them
null on every call, believing it had unlimited budget.

The client therefore counts its own requests against the published figures: 100 reads per
fifteen minutes and 1000 per day, counted per application rather than per user, with the short
window resetting on the quarter hour. A 429 is the only signal the browser actually gets, and it
is handled as the definitive one.

### Heart rate detail is one request per activity

The activity list is cheap: 200 activities per page, so a month of training is one or two
requests. The per-point heart rate series is a separate call for each activity, which is what
consumes the budget. Backfilling 300 activities with heart rate would take about 45 minutes of
wall clock against the new-application limit.

So the list is fetched when you connect, and streams are fetched only for the sessions actually
chosen for analysis, at the moment the analysis runs. Sessions whose stream has not been fetched
still carry the average and maximum heart rate from the summary, which is enough for a mean
fraction of heart rate reserve and not enough to tell a steady effort from intervals. The
intensity estimator marks that case as `summary` and declines to infer the shape of a session
from a mean.

## 3. The flow as implemented

| Step | Where |
|---|---|
| Register an application, callback domain `tim2000s.github.io` | the user, once, at strava.com/settings/api |
| Redirect to `/oauth/authorize` with `response_type=code`, `scope=activity:read_all` and a random `state` | `authoriseUrl` |
| Strava returns to this page with `?code=` and `?state=` | `readRedirect`, which checks the state and strips the query |
| Exchange the code at `/oauth/token` for an access token, a refresh token and an expiry | `exchangeCode` |
| Renew silently when the six-hour access token expires | `refreshTokens` |
| List activities in the chosen window | `fetchActivities` |
| Fetch heart rate for chosen sessions only | `fetchHeartRateFor` |

The authorisation page sends `x-frame-options: DENY`, so it cannot be shown in an iframe. A
full-page redirect is used.

The callback domain is a bare host with no scheme and no path; any path under that host is then
accepted as a redirect target. Note that `tim2000s.github.io` covers every repository published
on that host, not just this one. A custom domain would narrow it.

## 4. Fields the API gives, and one it does not

`GET /athlete/activities` takes `after` and `before` as epoch seconds and is exclusive at both
ends, so the client nudges the bounds outward by a second.

| Field | Unit | Note |
|---|---|---|
| `start_date` | ISO 8601 UTC | the session start |
| `elapsed_time` | seconds | wall clock, and therefore what the session window uses |
| `moving_time` | seconds | excludes pauses, so not comparable to a glucose trace |
| `distance` | metres | |
| `total_elevation_gain` | metres | |
| `average_heartrate`, `max_heartrate`, `has_heartrate` | bpm | absent from the published schema but returned |
| `sport_type` | enum of 56 values | preferred over the deprecated `type`, which has 37 |
| `calories` | | not returned by the list endpoint at all |

Calories would cost one `GET /activities/{id}` per activity, roughly doubling the request
budget, so the tool leaves them empty rather than paying for them. The bulk export carries them
in `activities.csv` for nothing.

The deprecated `type` field collapses distinctions that `sport_type` keeps: a gravel ride
reports `type: "Ride"` and `sport_type: "GravelRide"`. The client reads `sport_type` and falls
back to `type`.

Of the 56 sport types, 55 map onto a Health Connect exercise type. Skateboard has no equivalent
and is reported as unknown by name rather than silently guessed at.

## 5. The terms, which are worth reading before choosing this route

Strava's API Policy effective 1 June 2026 contains three clauses that sit awkwardly against any
analysis tool.

Section 6.2 caps retention: Strava Data may not be held in cache for longer than seven days.
Section 5.5 prohibits accumulating data through repeated API calls into a corpus or a persistent
index. Section 5.4 is the widest: it prohibits processing Strava Data, even in an aggregated or
anonymised form, for the purposes of analytics or analyses.

Sections 2.3 and 6.1 clearly contemplate an application showing a user their own data, and 2.2
requires letting users access what has been collected, so the policy is not aimed at personal
dashboards. It does not carve them out either.

What this tool does about it: activities fetched from Strava are held in memory for the length
of the visit and are never written to storage, so nothing is retained and no index is built. The
analysis runs on the user's own machine on their own data. Whether a strict reading of 5.4
permits that is not something a comment in a source file can settle.

Section 6.6 is unambiguous in the other direction:

> Each Strava user has the right to access and export the user's own Strava data, free of
> charge, through the Bulk Data Export Tool published on the Strava service. Nothing in this
> Agreement is intended to limit or condition that user-facing right.

The bulk export sits outside the API Agreement entirely, needs no subscription, no application
and no rate limiting, and carries calories and relative effort that the API list endpoint does
not. It is the better route on almost every axis except convenience, and the interface says so
where the choice is made.

## 6. Things not verified

Whether Strava's callback domain field rejects a Public Suffix List entry such as `github.io`
could not be tested without registering an application. The maximum accepted `per_page` is
undocumented; 200 is used and is widely reported to work. The scope attached to the access token
shown on the API settings page is not documented, and is commonly reported to be read-only,
which would be insufficient for activities.
