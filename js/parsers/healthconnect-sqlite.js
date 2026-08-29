// Reader for the Health Connect built-in export.
//
// The export is a deflate zip holding one entry, health_connect_export.db, which is a plain
// unencrypted SQLite 3 database. The schema is internal AOSP with no published contract, so
// every table is probed before it is read and a missing table degrades to an empty list
// rather than an error. See docs/health-connect-formats.md.

import { decodeExerciseType, modalityFor } from './exercise-types.js';

const KCAL_PER_STORED_CALORIE = 1 / 1000; // Energy is stored in calories, not kilocalories.
const MGDL_PER_MMOL = 18.0182;

/** Sniff whether a byte array is a SQLite database, by its 16-byte file header. */
export function isSqlite(bytes) {
  const magic = 'SQLite format 3\0';
  if (bytes.length < magic.length) return false;
  for (let i = 0; i < magic.length; i++) {
    if (bytes[i] !== magic.charCodeAt(i)) return false;
  }
  return true;
}

function tableExists(db, name) {
  const r = db.exec("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [name]);
  return r.length > 0 && r[0].values.length > 0;
}

function columnsOf(db, table) {
  try {
    const r = db.exec(`PRAGMA table_info(${JSON.stringify(table)})`);
    if (!r.length) return new Set();
    const nameIdx = r[0].columns.indexOf('name');
    return new Set(r[0].values.map((row) => row[nameIdx]));
  } catch {
    return new Set();
  }
}

/** Run a query and return an array of plain objects keyed by column name. */
function rows(db, sql, params) {
  const out = [];
  const stmt = db.prepare(sql);
  try {
    if (params) stmt.bind(params);
    while (stmt.step()) out.push(stmt.getAsObject());
  } finally {
    stmt.free();
  }
  return out;
}

/**
 * Indexes are created on the copy held in memory because the per-session range queries below
 * would otherwise scan the whole sample table once per session. A year of continuous heart
 * rate is on the order of 10^5 to 10^6 rows, and two hundred sessions against that is slow
 * enough to be felt. Building the index costs one sort.
 */
function ensureIndexes(db, warnings) {
  const wanted = [
    ['heart_rate_record_series_table', 'epoch_millis'],
    ['speed_record_table', 'epoch_millis'],
    ['power_record_table', 'epoch_millis'],
    ['steps_record_table', 'start_time'],
    ['distance_record_table', 'start_time'],
    ['active_calories_burned_record_table', 'start_time'],
    ['total_calories_burned_record_table', 'start_time'],
    ['elevation_gained_record_table', 'start_time'],
    ['exercise_session_record_table', 'start_time'],
  ];
  for (const [table, col] of wanted) {
    if (!tableExists(db, table)) continue;
    if (!columnsOf(db, table).has(col)) continue;
    try {
      db.run(`CREATE INDEX IF NOT EXISTS xeval_ix_${table}_${col} ON ${table}(${col})`);
    } catch (e) {
      warnings.push(`Could not index ${table}(${col}): ${e.message}. Parsing will be slower.`);
    }
  }
}

/**
 * Sum a value column over records whose interval overlaps [start, end], apportioning by the
 * fraction of each record that falls inside the window.
 *
 * Apportioning matters because Health Connect writers commonly emit step and distance records
 * on their own cadence, often a fixed bucket, which straddles the start and end of a session.
 * Taking whole records overstates a short session; ignoring partial ones understates it. The
 * apportioning assumes the quantity accrued at a constant rate across the record, which is a
 * modelling choice and is wrong in detail for a bucket containing a sprint.
 */
function sumOverlap(db, table, valueCol, start, end) {
  if (!tableExists(db, table)) return null;
  const cols = columnsOf(db, table);
  if (!cols.has(valueCol) || !cols.has('start_time') || !cols.has('end_time')) return null;
  const rs = rows(
    db,
    `SELECT start_time, end_time, ${valueCol} AS v FROM ${table}
      WHERE end_time > ? AND start_time < ? AND ${valueCol} IS NOT NULL`,
    [start, end],
  );
  if (!rs.length) return null;
  let total = 0;
  for (const r of rs) {
    const span = r.end_time - r.start_time;
    if (span <= 0) {
      total += r.v;
      continue;
    }
    const lo = Math.max(r.start_time, start);
    const hi = Math.min(r.end_time, end);
    total += r.v * ((hi - lo) / span);
  }
  return total;
}

function seriesInWindow(db, table, timeCol, valueCol, start, end, maxPoints = 3000) {
  if (!tableExists(db, table)) return [];
  const cols = columnsOf(db, table);
  if (!cols.has(timeCol) || !cols.has(valueCol)) return [];
  const rs = rows(
    db,
    `SELECT ${timeCol} AS t, ${valueCol} AS v FROM ${table}
      WHERE ${timeCol} >= ? AND ${timeCol} <= ? AND ${valueCol} IS NOT NULL
      ORDER BY ${timeCol}`,
    [start, end],
  );
  if (rs.length <= maxPoints) return rs.map((r) => ({ t: r.t, v: r.v }));
  const stride = Math.ceil(rs.length / maxPoints);
  const out = [];
  for (let i = 0; i < rs.length; i += stride) out.push({ t: rs[i].t, v: rs[i].v });
  return out;
}

function uuidHex(blob) {
  if (!blob) return null;
  if (typeof blob === 'string') return blob;
  return Array.from(blob, (b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Parse an opened sql.js database into the tool's internal shape.
 *
 * @param {object} db an open sql.js Database
 * @returns {object} parsed dataset
 */
export function parseHealthConnectDb(db) {
  const warnings = [];
  let dbVersion = null;
  try {
    const r = db.exec('PRAGMA user_version');
    dbVersion = r.length ? r[0].values[0][0] : null;
  } catch {
    warnings.push('Could not read PRAGMA user_version.');
  }

  ensureIndexes(db, warnings);

  const apps = new Map();
  if (tableExists(db, 'application_info_table')) {
    for (const r of rows(db, 'SELECT row_id, app_name, package_name FROM application_info_table')) {
      apps.set(r.row_id, { name: r.app_name, pkg: r.package_name });
    }
  }

  const sessions = [];
  if (!tableExists(db, 'exercise_session_record_table')) {
    warnings.push(
      'No exercise_session_record_table in this database. The export contains no workout ' +
        'sessions, which usually means no app on the phone was writing them to Health Connect.',
    );
  } else {
    const sCols = columnsOf(db, 'exercise_session_record_table');
    const pick = (c) => (sCols.has(c) ? c : `NULL AS ${c}`);
    const sql = `SELECT row_id, uuid, start_time, end_time,
                        ${pick('start_zone_offset')}, ${pick('end_zone_offset')},
                        ${pick('exercise_type')}, ${pick('title')}, ${pick('notes')},
                        ${pick('app_info_id')}
                 FROM exercise_session_record_table ORDER BY start_time`;
    for (const r of rows(db, sql)) {
      const start = r.start_time;
      const end = r.end_time;
      if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
        warnings.push(`Skipped a session with an unusable time range (row ${r.row_id}).`);
        continue;
      }
      const type = decodeExerciseType(r.exercise_type, 'platform');
      const hr = seriesInWindow(db, 'heart_rate_record_series_table', 'epoch_millis',
        'beats_per_minute', start, end);
      const activeCal = sumOverlap(db, 'active_calories_burned_record_table', 'energy', start, end);
      const totalCal = sumOverlap(db, 'total_calories_burned_record_table', 'energy', start, end);
      const app = apps.get(r.app_info_id);

      sessions.push({
        id: uuidHex(r.uuid) || `row-${r.row_id}`,
        start,
        end,
        durationMin: (end - start) / 60000,
        startOffsetSec: r.start_zone_offset ?? null,
        endOffsetSec: r.end_zone_offset ?? null,
        typeName: type.name,
        typeRaw: type.raw,
        typeKnown: type.known,
        modality: modalityFor(type.name),
        title: r.title || null,
        notes: r.notes || null,
        sourceApp: app ? app.name || app.pkg : null,
        distanceM: sumOverlap(db, 'distance_record_table', 'distance', start, end),
        steps: sumOverlap(db, 'steps_record_table', 'count', start, end),
        elevationM: sumOverlap(db, 'elevation_gained_record_table', 'elevation', start, end),
        activeKcal: activeCal === null ? null : activeCal * KCAL_PER_STORED_CALORIE,
        totalKcal: totalCal === null ? null : totalCal * KCAL_PER_STORED_CALORIE,
        hr: hr.map((p) => ({ t: p.t, bpm: p.v })),
        speed: seriesInWindow(db, 'speed_record_table', 'epoch_millis', 'speed', start, end, 1000),
        power: seriesInWindow(db, 'power_record_table', 'epoch_millis', 'power', start, end, 1000),
        segments: tableExists(db, 'exercise_segments_table')
          ? rows(db, `SELECT segment_start_time AS start, segment_end_time AS end,
                             segment_type AS type, repetitions_count AS reps
                      FROM exercise_segments_table WHERE parent_key = ?`, [r.row_id])
          : [],
        laps: tableExists(db, 'exercise_laps_table')
          ? rows(db, `SELECT lap_start_time AS start, lap_end_time AS end, lap_length AS lengthM
                      FROM exercise_laps_table WHERE parent_key = ?`, [r.row_id])
          : [],
      });
    }
  }

  // Resting heart rate is used to anchor heart rate reserve when the user has not entered a
  // value by hand. The most recent reading before each session is the one applied.
  const restingHr = tableExists(db, 'resting_heart_rate_record_table')
    ? rows(db, `SELECT time AS t, beats_per_minute AS bpm
                FROM resting_heart_rate_record_table
                WHERE beats_per_minute IS NOT NULL ORDER BY time`)
    : [];

  const vo2max = tableExists(db, 'vo2_max_record_table')
    ? rows(db, `SELECT time AS t, vo2_milliliters_per_minute_kilogram AS vo2,
                       measurement_method AS method FROM vo2_max_record_table ORDER BY time`)
    : [];

  // Blood glucose here is stored in mmol/L, unlike Nightscout which stores mg/dL internally.
  const glucose = tableExists(db, 'blood_glucose_record_table')
    ? rows(db, `SELECT time AS t, level, relation_to_meal, meal_type
                FROM blood_glucose_record_table WHERE level IS NOT NULL ORDER BY time`)
        .map((r) => ({ t: r.t, mmol: r.level, mgdl: r.level * MGDL_PER_MMOL }))
    : [];

  const nutrition = tableExists(db, 'nutrition_record_table')
    && columnsOf(db, 'nutrition_record_table').has('total_carbohydrate')
    ? rows(db, `SELECT start_time AS start, end_time AS end, total_carbohydrate AS carbsG,
                       meal_name AS name, meal_type AS mealType
                FROM nutrition_record_table WHERE total_carbohydrate IS NOT NULL
                ORDER BY start_time`)
    : [];

  const sleep = tableExists(db, 'sleep_session_record_table')
    ? rows(db, `SELECT start_time AS start, end_time AS end, title
                FROM sleep_session_record_table ORDER BY start_time`)
    : [];

  if (dbVersion !== null && dbVersion < 10) {
    warnings.push(
      `Database schema version ${dbVersion} predates the generated local-time columns. Local ` +
        'times are derived from the stored zone offsets instead, which is equivalent.',
    );
  }

  return {
    source: 'health-connect-sqlite',
    meta: {
      dbVersion,
      apps: [...apps.values()],
      sessionCount: sessions.length,
      hrSampleTotal: sessions.reduce((a, s) => a + s.hr.length, 0),
    },
    sessions,
    restingHr,
    vo2max,
    glucose,
    nutrition,
    sleep,
    warnings,
  };
}
