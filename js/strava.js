// Strava client, for a browser with no server of its own.
//
// This works, which is not obvious in advance. Strava sends Access-Control-Allow-Origin: * on
// both the API and the token exchange, and its preflight explicitly allows the authorization
// header, so a static page can complete the whole authorisation code flow and read the API
// afterwards. Verified against the live endpoints rather than inferred from documentation.
//
// What it costs the user is a Strava API application of their own, because the token exchange
// requires a client secret and Strava does not support PKCE. That secret is theirs, it is for
// their own data, and it never leaves their browser. The interface says so, and offers to
// forget it.
//
// The expensive call is the per-activity heart rate stream, one request each against a read
// budget of about 100 per fifteen minutes. The activity list is therefore fetched up front and
// streams are fetched only for the sessions actually chosen for analysis.

import { decodeExerciseType, modalityFor } from './parsers/exercise-types.js';

const API = 'https://www.strava.com/api/v3';
const OAUTH = 'https://www.strava.com/oauth';

/** Read scope. activity:read_all also covers activities the user marked private. */
export const SCOPE = 'activity:read_all';

/** Left in reserve when pacing requests, so a run never consumes the user's whole budget. */
const RESERVE_REQUESTS = 10;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** The redirect target, which is this page with any query string stripped. */
export function redirectUri() {
  return `${location.origin}${location.pathname}`;
}

/**
 * The URL to send the user to.
 *
 * The state is a random value kept in sessionStorage and checked on return, so a code delivered
 * to this page by anything other than the flow it started is rejected.
 */
export function authoriseUrl(clientId) {
  const state = crypto.randomUUID();
  try { sessionStorage.setItem('strava.state', state); } catch { /* private window */ }
  const params = new URLSearchParams({
    client_id: clientId,
    response_type: 'code',
    redirect_uri: redirectUri(),
    approval_prompt: 'auto',
    scope: SCOPE,
    state,
  });
  return `${OAUTH}/authorize?${params}`;
}

/**
 * Read an authorisation result out of the current URL, if this load is a return from Strava.
 *
 * @returns {{code: string}|{error: string}|null}
 */
export function readRedirect() {
  const q = new URLSearchParams(location.search);
  const code = q.get('code');
  const error = q.get('error');
  if (!code && !error) return null;

  let expected = null;
  try { expected = sessionStorage.getItem('strava.state'); } catch { /* ignore */ }
  try { sessionStorage.removeItem('strava.state'); } catch { /* ignore */ }

  // Clear the query string so a reload does not attempt the same one-time code again.
  history.replaceState(null, '', redirectUri());

  if (error) return { error: `Strava returned "${error}". Authorisation was not completed.` };
  if (expected && q.get('state') !== expected) {
    return { error: 'The authorisation response did not match the request this page started, ' +
                    'so it was discarded.' };
  }
  const scope = q.get('scope') || '';
  if (!scope.includes('activity:read')) {
    return { error: 'Authorisation completed without permission to read activities. Tick the ' +
                    'activity permission on the Strava screen and try again.' };
  }
  return { code };
}

async function postForm(path, body) {
  const res = await fetch(`${OAUTH}/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(body),
    credentials: 'omit',
  });
  const text = await res.text();
  let data = null;
  try { data = JSON.parse(text); } catch { /* Strava returned something unexpected */ }
  if (!res.ok) {
    const detail = data?.message || text.slice(0, 200) || res.statusText;
    const field = data?.errors?.[0]?.field;
    if (res.status === 400 && field === 'client_id') {
      throw new Error('Strava rejected the client ID. Check it against your API application at ' +
                      'strava.com/settings/api.');
    }
    if (res.status === 400 && field === 'code') {
      throw new Error('Strava rejected the authorisation code. These are single use, so start ' +
                      'the connection again.');
    }
    if (res.status === 401) {
      throw new Error('Strava rejected the client secret. Check it against your API application.');
    }
    throw new Error(`Strava token exchange failed: ${detail}`);
  }
  return data;
}

/** Exchange a one-time code for tokens. */
export async function exchangeCode(clientId, clientSecret, code) {
  const d = await postForm('token', {
    client_id: clientId, client_secret: clientSecret, code, grant_type: 'authorization_code',
  });
  return {
    accessToken: d.access_token,
    refreshToken: d.refresh_token,
    expiresAt: d.expires_at * 1000,
    athlete: d.athlete ? { id: d.athlete.id, name: [d.athlete.firstname, d.athlete.lastname]
      .filter(Boolean).join(' ') } : null,
  };
}

/** Trade a refresh token for a fresh access token. Strava access tokens last six hours. */
export async function refreshTokens(clientId, clientSecret, refreshToken) {
  const d = await postForm('token', {
    client_id: clientId, client_secret: clientSecret,
    refresh_token: refreshToken, grant_type: 'refresh_token',
  });
  return {
    accessToken: d.access_token,
    refreshToken: d.refresh_token || refreshToken,
    expiresAt: d.expires_at * 1000,
  };
}

/**
 * A request budget kept on this side, because Strava's own figures cannot be read.
 *
 * Strava returns X-RateLimit-Usage and X-ReadRateLimit-Usage on every authenticated response,
 * but sends no Access-Control-Expose-Headers, so browser JavaScript is not permitted to read
 * them. An earlier version of this file parsed those headers and would have found them null on
 * every call, silently believing it had unlimited budget. Counting here is the only option, and
 * a 429 is the only signal the browser actually gets.
 *
 * The published read limits for a new application are 100 requests per 15 minutes and 1000 per
 * day, per application rather than per user. The window resets on the quarter hour rather than
 * rolling, so the count is cleared when the quarter changes.
 */
export const READ_LIMIT_PER_WINDOW = 100;
const WINDOW_MS = 15 * 60 * 1000;

const budget = { windowStart: 0, used: 0 };

function quarterHourStart(now = Date.now()) {
  return Math.floor(now / WINDOW_MS) * WINDOW_MS;
}

/** Requests left in the current quarter hour, less the reserve. */
export function requestsLeft() {
  const start = quarterHourStart();
  if (start !== budget.windowStart) return READ_LIMIT_PER_WINDOW - RESERVE_REQUESTS;
  return Math.max(0, READ_LIMIT_PER_WINDOW - RESERVE_REQUESTS - budget.used);
}

function spend() {
  const start = quarterHourStart();
  if (start !== budget.windowStart) {
    budget.windowStart = start;
    budget.used = 0;
  }
  budget.used += 1;
}

/** Minutes until the current quarter-hour window resets. */
export function minutesUntilReset() {
  return Math.ceil((quarterHourStart() + WINDOW_MS - Date.now()) / 60000);
}

/** Exposed so tests can start from a known position. */
export function resetBudget() {
  budget.windowStart = 0;
  budget.used = 0;
}

async function apiGet(path, token, params = {}) {
  const url = new URL(`${API}/${path}`);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  }
  spend();
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
    credentials: 'omit',
  });

  if (res.status === 401) {
    const e = new Error('Strava rejected the access token. It may have expired; reconnecting ' +
                        'will get a new one.');
    e.kind = 'auth';
    throw e;
  }
  if (res.status === 429) {
    const e = new Error(
      `Strava refused the request as over its rate limit. The read budget is 100 requests every ` +
      `fifteen minutes and 1000 a day, counted per application. This window resets in about ` +
      `${minutesUntilReset()} minutes.`);
    e.kind = 'rate-limit';
    throw e;
  }
  if (!res.ok) {
    throw new Error(`Strava returned ${res.status} ${res.statusText} for ${path}.`);
  }
  return { data: await res.json() };
}

/**
 * Every activity that started within a window, newest first from Strava and returned oldest
 * first here.
 *
 * The list endpoint takes epoch seconds and is exclusive at both ends, so the bounds are nudged
 * outwards by a second to avoid dropping an activity that starts exactly on the boundary.
 */
export async function fetchActivities(token, fromMs, toMs, onProgress = () => {}) {
  const out = [];
  let page = 1;

  for (;;) {
    const { data } = await apiGet('athlete/activities', token, {
      after: Math.floor(fromMs / 1000) - 1,
      before: Math.ceil(toMs / 1000) + 1,
      per_page: 200,
      page,
    });
    if (!Array.isArray(data) || data.length === 0) break;
    out.push(...data);
    onProgress(`Fetched ${out.length} activities from Strava.`);
    if (data.length < 200) break;
    page += 1;
    if (page > 25) break;             // 5000 activities in one window is not a real case
    await sleep(150);
  }
  return { activities: out };
}

/**
 * The heart rate series for one activity.
 *
 * Streams are returned as parallel arrays keyed by type. The time stream is seconds from the
 * start of the activity, so it is rebased onto wall clock here. An activity recorded without a
 * heart rate monitor returns 404 for the heartrate key, which is not an error worth reporting.
 */
export async function fetchHeartRate(token, activityId, startMs) {
  try {
    const { data } = await apiGet(`activities/${activityId}/streams`, token, {
      keys: 'heartrate,time', key_by_type: true,
    });
    const hr = data?.heartrate?.data;
    const time = data?.time?.data;
    if (!Array.isArray(hr) || !Array.isArray(time)) return { hr: [] };
    const n = Math.min(hr.length, time.length);
    const out = [];
    for (let i = 0; i < n; i++) {
      if (Number.isFinite(hr[i])) out.push({ t: startMs + time[i] * 1000, bpm: hr[i] });
    }
    return { hr: out };
  } catch (e) {
    if (e.kind === 'rate-limit' || e.kind === 'auth') throw e;
    return { hr: [], error: e.message };
  }
}

/** Strava's own name for the activity, preferring the newer field. */
const sportOf = (a) => a.sport_type || a.type || '';

/** Convert Strava activities into the shape the rest of the tool works in. */
export function toSessions(activities) {
  const sessions = [];
  const warnings = [];
  let noHeartRate = 0;

  for (const a of activities) {
    const start = Date.parse(a.start_date);
    // elapsed_time is wall clock and moving_time excludes pauses. A session's window has to be
    // wall clock, because the glucose record is.
    const seconds = a.elapsed_time || a.moving_time;
    if (!Number.isFinite(start) || !Number.isFinite(seconds) || seconds <= 0) {
      warnings.push(`Skipped Strava activity ${a.id} because its times were unusable.`);
      continue;
    }
    const type = decodeExerciseType(sportOf(a), 'jetpack');
    if (!a.has_heartrate) noHeartRate += 1;

    sessions.push({
      id: `strava-${a.id}`,
      stravaId: a.id,
      start,
      end: start + seconds * 1000,
      durationMin: seconds / 60,
      startOffsetSec: Number.isFinite(a.utc_offset) ? a.utc_offset : null,
      endOffsetSec: Number.isFinite(a.utc_offset) ? a.utc_offset : null,
      typeName: type.name,
      typeRaw: sportOf(a),
      typeKnown: type.known,
      modality: modalityFor(type.name),
      title: a.name || null,
      notes: null,
      sourceApp: 'Strava',
      distanceM: Number.isFinite(a.distance) ? a.distance : null,
      steps: null,
      elevationM: Number.isFinite(a.total_elevation_gain) ? a.total_elevation_gain : null,
      // The list endpoint omits calories; only the detailed activity carries it.
      activeKcal: Number.isFinite(a.calories) ? a.calories : null,
      totalKcal: null,
      avgHr: Number.isFinite(a.average_heartrate) ? a.average_heartrate : null,
      maxHr: Number.isFinite(a.max_heartrate) ? a.max_heartrate : null,
      hasHeartRate: Boolean(a.has_heartrate),
      // The series is fetched later, and only for sessions chosen for analysis.
      hr: [],
      speed: [], power: [], segments: [], laps: [],
    });
  }

  const unknown = sessions.filter((s) => !s.typeKnown);
  if (unknown.length) {
    const names = [...new Set(unknown.map((s) => s.typeRaw))].slice(0, 5).join(', ');
    warnings.push(
      `${unknown.length} activit${unknown.length === 1 ? 'y' : 'ies'} had a Strava sport this ` +
      `tool does not map (${names}). Their intensity will come from heart rate alone.`);
  }
  if (noHeartRate) {
    warnings.push(
      `${noHeartRate} of ${sessions.length} activities were recorded without a heart rate ` +
      'monitor, so their intensity rests on the activity label.');
  }

  sessions.sort((a, b) => a.start - b.start);
  return { source: 'strava', sessions, warnings,
           restingHr: [], vo2max: [], glucose: [], nutrition: [], sleep: [],
           meta: { activities: activities.length } };
}

/**
 * Fetch heart rate for a set of sessions, pacing against the rate limit.
 *
 * Stops rather than exhausting the budget, because a user who cannot make another Strava
 * request for fifteen minutes has a worse problem than a few sessions without heart rate.
 */
export async function fetchHeartRateFor(token, sessions, onProgress = () => {}) {
  const wanted = sessions.filter((s) => s.stravaId && s.hasHeartRate && !s.hr.length);
  if (!wanted.length) return { fetched: 0, warnings: [] };

  const warnings = [];
  let fetched = 0;

  for (const [i, s] of wanted.entries()) {
    if (requestsLeft() <= 0) {
      warnings.push(
        `Stopped after ${fetched} of ${wanted.length} sessions, having used this fifteen minute ` +
        `window's request budget. The rest keep the average and maximum heart rate from the ` +
        `activity summary, which still gives an intensity estimate. The window resets in about ` +
        `${minutesUntilReset()} minutes.`);
      break;
    }
    onProgress(`Fetching heart rate from Strava, ${i + 1} of ${wanted.length}.`);
    try {
      const { hr } = await fetchHeartRate(token, s.stravaId, s.start);
      if (hr.length) { s.hr = hr; fetched += 1; }
    } catch (e) {
      if (e.kind === 'rate-limit') {
        warnings.push(
          `${e.message} ${fetched} of ${wanted.length} sessions got their heart rate before the ` +
          'limit was reached.');
        break;
      }
      throw e;
    }
    await sleep(120);
  }
  return { fetched, warnings };
}
