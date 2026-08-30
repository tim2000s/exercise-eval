import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toSessions, requestsLeft, resetBudget, minutesUntilReset, READ_LIMIT_PER_WINDOW }
  from '../js/strava.js';

/** A Strava summary activity, in the shape the list endpoint returns. */
function activity(over = {}) {
  return {
    id: 9001,
    name: 'Evening run',
    sport_type: 'Run',
    type: 'Run',
    start_date: '2026-08-03T17:00:00Z',
    start_date_local: '2026-08-03T18:00:00Z',
    utc_offset: 3600,
    elapsed_time: 2700,
    moving_time: 2600,
    distance: 8200.5,
    total_elevation_gain: 45,
    average_heartrate: 148.3,
    max_heartrate: 171,
    has_heartrate: true,
    ...over,
  };
}

test('a Strava activity maps onto the tool\'s session shape with the right units', () => {
  const { sessions } = toSessions([activity()]);
  assert.equal(sessions.length, 1);
  const s = sessions[0];
  assert.equal(s.typeName, 'RUNNING');
  assert.equal(s.modality, 'aerobic');
  assert.equal(new Date(s.start).toISOString(), '2026-08-03T17:00:00.000Z');
  assert.equal(s.durationMin, 45);
  assert.equal(s.distanceM, 8200.5);      // metres, as Strava gives them
  assert.equal(s.elevationM, 45);
  assert.equal(s.avgHr, 148.3);
  assert.equal(s.maxHr, 171);
  assert.equal(s.sourceApp, 'Strava');
  assert.equal(s.stravaId, 9001);
});

test('the session window is wall clock, not moving time', () => {
  // The glucose record runs on wall clock, so a session that was paused still occupies the
  // whole period between its start and its end.
  const { sessions } = toSessions([activity({ elapsed_time: 3600, moving_time: 1800 })]);
  assert.equal(sessions[0].durationMin, 60);
});

test('the newer sport_type is preferred over the deprecated type', () => {
  // A gravel ride reports type "Ride" and sport_type "GravelRide".
  const { sessions } = toSessions([activity({ type: 'Ride', sport_type: 'GravelRide' })]);
  assert.equal(sessions[0].typeName, 'BIKING');
  assert.equal(sessions[0].typeRaw, 'GravelRide');
});

test('an activity with no heart rate is flagged rather than dropped', () => {
  const { sessions, warnings } = toSessions([
    activity({ has_heartrate: false, average_heartrate: undefined, max_heartrate: undefined }),
  ]);
  assert.equal(sessions.length, 1);
  assert.equal(sessions[0].hasHeartRate, false);
  assert.equal(sessions[0].avgHr, null);
  assert.ok(warnings.some((w) => /without a heart rate monitor/.test(w)));
});

test('calories are absent, because the list endpoint does not carry them', () => {
  // Getting calories costs one extra request per activity, which the rate limit does not allow.
  const { sessions } = toSessions([activity()]);
  assert.equal(sessions[0].activeKcal, null);
});

test('an unmapped sport is reported by name rather than silently treated as unknown', () => {
  const { sessions, warnings } = toSessions([activity({ sport_type: 'Skateboard' })]);
  assert.equal(sessions[0].typeName, 'UNKNOWN');
  assert.equal(sessions[0].typeKnown, false);
  assert.ok(warnings.some((w) => /Skateboard/.test(w)));
});

test('an activity with unusable times is skipped with a reason', () => {
  const { sessions, warnings } = toSessions([
    activity({ start_date: 'not a date' }),
    activity({ id: 9002, elapsed_time: 0, moving_time: 0 }),
    activity({ id: 9003 }),
  ]);
  assert.equal(sessions.length, 1);
  assert.equal(sessions[0].stravaId, 9003);
  assert.equal(warnings.filter((w) => /times were unusable/.test(w)).length, 2);
});

test('sessions come back oldest first', () => {
  const { sessions } = toSessions([
    activity({ id: 3, start_date: '2026-08-05T09:00:00Z' }),
    activity({ id: 1, start_date: '2026-08-01T09:00:00Z' }),
    activity({ id: 2, start_date: '2026-08-03T09:00:00Z' }),
  ]);
  assert.deepEqual(sessions.map((s) => s.stravaId), [1, 2, 3]);
});

test('the request budget is counted locally, since the headers cannot be read', () => {
  // Strava sends no Access-Control-Expose-Headers, so X-RateLimit-Usage is invisible to
  // browser JavaScript and the only usable signal is a 429.
  resetBudget();
  const start = requestsLeft();
  assert.ok(start > 0 && start < READ_LIMIT_PER_WINDOW,
    `the budget should hold a reserve back, got ${start} of ${READ_LIMIT_PER_WINDOW}`);
});

test('the window reset is reported in minutes and always inside a quarter hour', () => {
  const m = minutesUntilReset();
  assert.ok(m >= 0 && m <= 15, `reset in ${m} minutes`);
});
