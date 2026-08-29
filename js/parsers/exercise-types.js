// Health Connect exercise type decoding.
//
// Two incompatible integer encodings exist for the same named set. The SQLite export written
// by the platform uses android.health.connect.datatypes.ExerciseSessionType, values 0 to 61
// contiguous. Any app built on the Jetpack client sees
// androidx.health.connect.client.records.ExerciseSessionRecord.EXERCISE_TYPE_*, values 0 to 83
// with gaps, so that is what a third-party CSV or JSON export is likely to carry.
//
// The overlap decodes to something in both schemes, so choosing the wrong one produces a full
// set of wrong labels and no parse error. Platform 33 is RUNNING, Jetpack 33 is
// GUIDED_BREATHING. Platform 0 is UNKNOWN, Jetpack 0 is OTHER_WORKOUT.
//
// See docs/health-connect-formats.md section 5.

// [platform int, jetpack int, canonical name]
const TYPE_TABLE = [
  [0, null, 'UNKNOWN'],
  [1, 2, 'BADMINTON'],
  [2, 4, 'BASEBALL'],
  [3, 5, 'BASKETBALL'],
  [4, 8, 'BIKING'],
  [5, 9, 'BIKING_STATIONARY'],
  [6, 10, 'BOOT_CAMP'],
  [7, 11, 'BOXING'],
  [8, 13, 'CALISTHENICS'],
  [9, 14, 'CRICKET'],
  [10, 16, 'DANCING'],
  [11, 26, 'EXERCISE_CLASS'],
  [12, 27, 'FENCING'],
  [13, 28, 'FOOTBALL_AMERICAN'],
  [14, 29, 'FOOTBALL_AUSTRALIAN'],
  [15, 31, 'FRISBEE_DISC'],
  [16, 32, 'GOLF'],
  [17, 33, 'GUIDED_BREATHING'],
  [18, 34, 'GYMNASTICS'],
  [19, 35, 'HANDBALL'],
  [20, 36, 'HIGH_INTENSITY_INTERVAL_TRAINING'],
  [21, 37, 'HIKING'],
  [22, 38, 'ICE_HOCKEY'],
  [23, 39, 'ICE_SKATING'],
  [24, 44, 'MARTIAL_ARTS'],
  [25, 46, 'PADDLING'],
  [26, 47, 'PARAGLIDING'],
  [27, 48, 'PILATES'],
  [28, 50, 'RACQUETBALL'],
  [29, 51, 'ROCK_CLIMBING'],
  [30, 52, 'ROLLER_HOCKEY'],
  [31, 53, 'ROWING'],
  [32, 55, 'RUGBY'],
  [33, 56, 'RUNNING'],
  [34, 57, 'RUNNING_TREADMILL'],
  [35, 58, 'SAILING'],
  [36, 59, 'SCUBA_DIVING'],
  [37, 60, 'SKATING'],
  [38, 61, 'SKIING'],
  [39, 62, 'SNOWBOARDING'],
  [40, 63, 'SNOWSHOEING'],
  [41, 64, 'SOCCER'],
  [42, 65, 'SOFTBALL'],
  [43, 66, 'SQUASH'],
  [44, 68, 'STAIR_CLIMBING'],
  [45, 70, 'STRENGTH_TRAINING'],
  [46, 71, 'STRETCHING'],
  [47, 72, 'SURFING'],
  [48, 73, 'SWIMMING_OPEN_WATER'],
  [49, 74, 'SWIMMING_POOL'],
  [50, 75, 'TABLE_TENNIS'],
  [51, 76, 'TENNIS'],
  [52, 78, 'VOLLEYBALL'],
  [53, 79, 'WALKING'],
  [54, 80, 'WATER_POLO'],
  [55, 81, 'WEIGHTLIFTING'],
  [56, 82, 'WHEELCHAIR'],
  [57, 83, 'YOGA'],
  [58, 0, 'OTHER_WORKOUT'],
  [59, 69, 'STAIR_CLIMBING_MACHINE'],
  [60, 25, 'ELLIPTICAL'],
  [61, 54, 'ROWING_MACHINE'],
];

export const PLATFORM_TYPES = new Map(TYPE_TABLE.map(([p, , n]) => [p, n]));
export const JETPACK_TYPES = new Map(
  TYPE_TABLE.filter(([, j]) => j !== null).map(([, j, n]) => [j, n]),
);

// Wear Health Services writes strings rather than integers. The mapping is many to one:
// 22 strength movements collapse to STRENGTH_TRAINING and 9 bodyweight movements to
// CALISTHENICS in the Jetpack library, so only the distinctions this tool acts on are kept.
const STRING_ALIASES = {
  back_extension: 'STRENGTH_TRAINING', barbell_shoulder_press: 'STRENGTH_TRAINING',
  bench_press: 'STRENGTH_TRAINING', bench_sit_up: 'STRENGTH_TRAINING',
  biceps_curl: 'STRENGTH_TRAINING', deadlift: 'STRENGTH_TRAINING',
  dumbbell_curl_right_arm: 'STRENGTH_TRAINING', dumbbell_curl_left_arm: 'STRENGTH_TRAINING',
  dumbbell_front_raise: 'STRENGTH_TRAINING', dumbbell_lateral_raise: 'STRENGTH_TRAINING',
  dumbbell_row: 'STRENGTH_TRAINING', dumbbell_triceps_extension_left_arm: 'STRENGTH_TRAINING',
  dumbbell_triceps_extension_right_arm: 'STRENGTH_TRAINING',
  dumbbell_triceps_extension_two_arm: 'STRENGTH_TRAINING',
  lat_pull_down: 'STRENGTH_TRAINING', lateral_raise: 'STRENGTH_TRAINING',
  leg_curl: 'STRENGTH_TRAINING', leg_extension: 'STRENGTH_TRAINING',
  leg_press: 'STRENGTH_TRAINING', shoulder_press: 'STRENGTH_TRAINING',
  squat: 'STRENGTH_TRAINING', upper_twist: 'STRENGTH_TRAINING',
  burpee: 'CALISTHENICS', crunch: 'CALISTHENICS', forward_twist: 'CALISTHENICS',
  jumping_jack: 'HIGH_INTENSITY_INTERVAL_TRAINING', jump_rope: 'HIGH_INTENSITY_INTERVAL_TRAINING',
  lunge: 'CALISTHENICS', mountain_climber: 'CALISTHENICS', plank: 'CALISTHENICS',
  pull_up: 'CALISTHENICS', push_up: 'CALISTHENICS', sit_up: 'CALISTHENICS',
  // Preserved typo in the Wear Health Services string set, commented as such in androidx source.
  para_gliding: 'PARAGLIDING',
};

const CANONICAL = new Set(TYPE_TABLE.map(([, , n]) => n));

/**
 * Decode an exercise type from whichever representation the source uses.
 *
 * @param {number|string} raw the value as it appeared in the file
 * @param {'platform'|'jetpack'} scheme which integer encoding applies. The SQLite export is
 *   'platform'; a third-party export built on the Jetpack client is 'jetpack'.
 * @returns {{name: string, raw: number|string, known: boolean}}
 */
export function decodeExerciseType(raw, scheme) {
  if (raw === null || raw === undefined || raw === '') {
    return { name: 'UNKNOWN', raw, known: false };
  }
  if (typeof raw === 'string' && !/^\d+$/.test(raw.trim())) {
    const key = raw.trim().toLowerCase().replace(/[\s-]+/g, '_');
    const upper = key.toUpperCase();
    if (CANONICAL.has(upper)) return { name: upper, raw, known: true };
    if (STRING_ALIASES[key]) return { name: STRING_ALIASES[key], raw, known: true };
    return { name: 'UNKNOWN', raw, known: false };
  }
  const n = Number(raw);
  const table = scheme === 'jetpack' ? JETPACK_TYPES : PLATFORM_TYPES;
  const name = table.get(n);
  return name ? { name, raw: n, known: true } : { name: 'UNKNOWN', raw: n, known: false };
}

/** Human-readable label, for display only. Never used as a key. */
export function labelFor(name) {
  return name
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
    .replace('High Intensity Interval Training', 'HIIT');
}

/**
 * Prior expectation of glycaemic behaviour from the activity label alone.
 *
 * This is a prior, not a measurement. Where heart rate data exists the analysis engine
 * overrides it with an intensity estimate from heart rate reserve, because a jog and a
 * threshold run share the label RUNNING and behave differently. Where no heart rate exists
 * the prior is all there is, and the report says so.
 */
const MODALITY = {
  aerobic: ['BIKING', 'BIKING_STATIONARY', 'RUNNING', 'RUNNING_TREADMILL', 'WALKING', 'HIKING',
    'SWIMMING_POOL', 'SWIMMING_OPEN_WATER', 'ROWING', 'ROWING_MACHINE', 'ELLIPTICAL',
    'SNOWSHOEING', 'PADDLING', 'STAIR_CLIMBING', 'STAIR_CLIMBING_MACHINE', 'WHEELCHAIR',
    'DANCING', 'SKATING', 'ICE_SKATING', 'SKIING'],
  anaerobic: ['HIGH_INTENSITY_INTERVAL_TRAINING', 'BOXING', 'MARTIAL_ARTS'],
  resistance: ['STRENGTH_TRAINING', 'WEIGHTLIFTING', 'CALISTHENICS'],
  mixed: ['SOCCER', 'BASKETBALL', 'RUGBY', 'FOOTBALL_AMERICAN', 'FOOTBALL_AUSTRALIAN',
    'HANDBALL', 'ICE_HOCKEY', 'ROLLER_HOCKEY', 'TENNIS', 'SQUASH', 'BADMINTON', 'RACQUETBALL',
    'TABLE_TENNIS', 'VOLLEYBALL', 'CRICKET', 'BASEBALL', 'SOFTBALL', 'WATER_POLO', 'BOOT_CAMP',
    'EXERCISE_CLASS', 'GYMNASTICS', 'ROCK_CLIMBING', 'SURFING', 'SNOWBOARDING', 'FENCING',
    'FRISBEE_DISC'],
  low: ['YOGA', 'STRETCHING', 'PILATES', 'GUIDED_BREATHING', 'GOLF', 'SAILING', 'PARAGLIDING',
    'SCUBA_DIVING'],
};

const MODALITY_OF = new Map();
for (const [mod, names] of Object.entries(MODALITY)) {
  for (const n of names) MODALITY_OF.set(n, mod);
}

/** @returns {'aerobic'|'anaerobic'|'resistance'|'mixed'|'low'|'unknown'} */
export function modalityFor(name) {
  return MODALITY_OF.get(name) || 'unknown';
}
