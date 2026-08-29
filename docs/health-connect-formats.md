# Health Connect and activity file formats

Reference for the importers in `js/parsers/`. Field names, units and enum values were read
from AOSP and androidx source rather than from secondary documentation, because the export
schema is internal and carries no published contract.

Verification key: [SRC] read from AOSP or androidx source, [DOC] from Google's published
documentation, [3P] from a third-party open source project, [INF] inferred.

## 1. The built-in Health Connect export

The export is not encrypted and not password protected, despite a claim to the contrary that
circulates widely and appears in a stale Javadoc comment on the AOSP class itself. The code
below that comment uses `java.util.zip.ZipOutputStream` with no cipher. [SRC]

| Property | Value |
|---|---|
| Delivered filename | `Health Connect.zip`, user-renameable at setup [DOC] |
| Internal constant | `health_connect_export.zip` [SRC] |
| ZIP entries | Exactly one [SRC] |
| Entry name | `health_connect_export.db` [SRC] |
| Compression | Standard deflate [SRC] |
| Encryption | None [SRC] |
| Payload | Plain SQLite 3 database [SRC] |
| Schedule | Daily, weekly or monthly to a cloud storage app. No on-demand export [DOC] |

Source: `packages/modules/HealthFitness/service/java/com/android/server/healthconnect/exportimport/`,
files `ExportManager.java` and `Compressor.java`.

### What is stripped

`ExportManager.TABLES_TO_CLEAR` empties `access_logs_table` and `change_logs_table`. The
Personal Health Record tables are cleared when the relevant flag is set. Everything else
survives, including exercise route location data at full precision. Users are told this in
the importer UI before they select a file, since the tool never uploads it anywhere but the
point stands for any file they might share elsewhere.

### Schema versioning

Read `PRAGMA user_version` and branch on it. The version constants in
`flags/src/com/android/healthfitness/flags/DatabaseVersions.java` run 9 to 17 with
`LAST_ROLLED_OUT_DB_VERSION = 14` [SRC], while a third-party tool reports verifying against
`user_version 23` on a real device [3P]. That discrepancy is unresolved and is the argument
for reading the pragma rather than assuming. Milestones: v9 UUIDs became 16-byte BLOBs, v10
generated local-time columns appeared, v12/13 planned exercise sessions, v14 mindfulness.

## 2. Time and zone offsets

Uniform across every record table [SRC], and the thing most likely to be mishandled.

Interval records (sessions, steps, distance, calories):

| Column | Meaning |
|---|---|
| `start_time`, `end_time` | Epoch milliseconds UTC |
| `start_zone_offset`, `end_zone_offset` | Offset from UTC in seconds, not hours or minutes |
| `local_date_time_start_time` | Generated, `start_time + 1000 * start_zone_offset` |
| `local_date` | Local calendar day key |

Instantaneous records use `time`, `zone_offset`, `local_date_time`, `local_date` with the
same semantics.

The generated local-time columns hold a wall clock expressed as if it were an epoch. Passing
one to `new Date(ms)` shows the correct clock face only if it is then read with UTC
accessors. Zone offset is nullable, so nulls occur and the fallback to the viewer's zone is
surfaced rather than hidden.

## 3. Stored units

These are internal canonical units and they are not always the units the Jetpack API
presents. [SRC], read from the `*RecordInternal` conversion calls.

| Quantity | Stored unit | Conversion |
|---|---|---|
| Energy | calories, not kilocalories | divide by 1000 for kcal |
| Distance, elevation, lap length, altitude, accuracy | metres | |
| Speed | metres per second | |
| Power | watts | |
| Blood glucose | mmol/L | multiply by 18.0182 for mg/dL |
| Nutrition masses | grams | |
| Heart rate | beats per minute | |
| HRV RMSSD | milliseconds | |
| VO2 max | mL/min/kg | |

Energy carries the highest risk. A 500 kcal run is stored as 500000. Labelling that kcal
reports a 500,000 kcal workout, which is visibly absurd; dividing by 4.184 on the assumption
it is joules reports something wrong and plausible.

## 4. Table map

| Record type | Parent table | Child table |
|---|---|---|
| ExerciseSession | `exercise_session_record_table` | `exercise_segments_table`, `exercise_laps_table`, `exercise_route_table` |
| HeartRate | `heart_rate_record_table` | `heart_rate_record_series_table` |
| Speed | `SpeedRecordTable` | `speed_record_table` |
| Power | `PowerRecordTable` | `power_record_table` |
| SleepSession | `sleep_session_record_table` | `sleep_stages_table` |
| Steps | `steps_record_table` | |
| Distance | `distance_record_table` | |
| TotalCaloriesBurned | `total_calories_burned_record_table` | |
| ActiveCaloriesBurned | `active_calories_burned_record_table` | |
| ElevationGained | `elevation_gained_record_table` | |
| RestingHeartRate | `resting_heart_rate_record_table` | |
| HeartRateVariabilityRmssd | `heart_rate_variability_rmssd_record_table` | |
| Vo2Max | `vo2_max_record_table` | |
| BloodGlucose | `blood_glucose_record_table` | |
| Nutrition | `nutrition_record_table` | |
| App metadata | `application_info_table` | |
| Device metadata | `device_info_table` | |

Speed and power carry a naming trap [SRC]. `SpeedRecordHelper.TABLE_NAME` is `SpeedRecordTable`
in CamelCase and holds the parent interval row, while `SERIES_TABLE_NAME` is
`speed_record_table` in snake_case and holds individual samples. Power is identical. A parser
reading `speed_record_table` expecting one row per interval gets one row per sample. Heart
rate does not share the quirk: parent `heart_rate_record_table`, samples
`heart_rate_record_series_table`.

Every child table links by `parent_key INTEGER NOT NULL` referencing the parent `row_id`.

Base columns on every record table: `row_id`, `uuid` (16 raw bytes, not a hyphenated string),
`client_record_id`, `client_record_version`, `app_info_id`, `device_info_id`,
`last_modified_time`, `recording_method`, `dedupe_hash`.

Type-specific columns of interest:

- `exercise_session_record_table`: `exercise_type`, `title`, `notes`, `has_route`, `planned_exercise_session_id`
- `exercise_segments_table`: `segment_start_time`, `segment_end_time`, `segment_type`, `repetitions_count`
- `exercise_laps_table`: `lap_start_time`, `lap_end_time`, `lap_length` (metres)
- `exercise_route_table`: `timestamp_millis`, `latitude`, `longitude`, `altitude`, `horizontal_accuracy`, `vertical_accuracy`
- `heart_rate_record_series_table`: `epoch_millis`, `beats_per_minute`
- `steps_record_table`: `count`; `distance_record_table`: `distance`; both calorie tables: `energy`
- `nutrition_record_table`: about 40 nutrient columns in snake_case. Carbohydrate is `total_carbohydrate`
- `blood_glucose_record_table`: `level`, `specimen_source`, `relation_to_meal`, `meal_type`

Health Connect does not attach distance, calories or heart rate to a session object. Those
are separate record types, correlated to a workout only by overlapping time window, so any
per-workout distance or calorie figure is computed by the parser as an interval join on
`start_time` and `end_time`.

## 5. The two exercise type enums

There are two incompatible integer encodings of the same named set [SRC]:

- Platform, `android.health.connect.datatypes.ExerciseSessionType`, values 0 to 61 contiguous.
  This is what is written to `exercise_session_record_table.exercise_type`.
- Jetpack, `androidx.health.connect.client.records.ExerciseSessionRecord.EXERCISE_TYPE_*`,
  values 0 to 83 with 23 gaps. This is what any app built on the Jetpack client sees, so it
  is what a third-party CSV or JSON export most likely contains.

They are bridged by a name-keyed map in `IntDefMappings.kt`, which is direct evidence they
are not the same numbers. The collision that makes this dangerous: platform 0 is UNKNOWN
while Jetpack 0 is OTHER_WORKOUT, and platform 33 is RUNNING while Jetpack 33 is
GUIDED_BREATHING. Every value in the overlap decodes to something, so a wrong choice of table
yields a full set of wrong labels with no parse error.

The mapping table lives in `js/parsers/exercise-types.js` and is mirrored in
`python/xeval/exercise_types.py`. Jetpack values absent from the mapping (1, 3, 6, 7, 12, 15,
17 to 24, 30, 40 to 43, 45, 49, 67, 77) are unassigned in the current library. An
unrecognised integer is treated as unknown and the raw value preserved.

Segments have the same dual-numbering problem with a different permutation again. Platform
RUNNING is 16 while Jetpack RUNNING is 46; platform 62 is HIGH_INTENSITY_INTERVAL_TRAINING
while Jetpack 62 is SWIMMING_POOL.

### Other enums

Sleep stage: 0 UNKNOWN, 1 AWAKE, 2 SLEEPING, 3 OUT_OF_BED, 4 LIGHT, 5 DEEP, 6 REM, 7 AWAKE_IN_BED.
VO2 max method: 0 OTHER, 1 METABOLIC_CART, 2 HEART_RATE_RATIO, 3 COOPER_TEST, 4 MULTISTAGE_FITNESS_TEST, 5 ROCKPORT_FITNESS_TEST.
Glucose specimen source: 0 UNKNOWN, 1 INTERSTITIAL_FLUID, 2 CAPILLARY_BLOOD, 3 PLASMA, 4 SERUM, 5 TEARS, 6 WHOLE_BLOOD.
Glucose relation to meal: 0 UNKNOWN, 1 GENERAL, 2 FASTING, 3 BEFORE_MEAL, 4 AFTER_MEAL.
Meal type: 0 UNKNOWN, 1 BREAKFAST, 2 LUNCH, 3 DINNER, 4 SNACK.

## 6. Third-party exporters

No third-party Android exporter was found with a public repository that writes a CSV for
exercise sessions with a documented header line. The two apps most marketed for this are
closed source and publish no schema. Planning a parser around a specific layout is therefore
not possible from documentation, which is why the CSV importer sniffs the header row and maps
columns at runtime, with a manual override in the UI.

| App | Output | Exercise records | Source readable |
|---|---|---|---|
| Health Data Export (teqxnology) | CSV, Google Sheets | Supported, no schema published | No |
| Health Sync (appyhapps.nl) | CSV for metrics; CSV, FIT, TCX, GPX, KML for activities | Vendor describes a high-level summary | No |
| Health.md (isolated.tech) | Markdown, JSON, CSV | Versioned `schema_version` v0 to v9, route array or sidecar | Reader only |
| OpenVitals (mmarca-tech) | GPX or KMZ per workout | Yes, lat/lon to 7 dp, elevation in metres, ISO 8601 times | Yes |
| HealthConnect_to_HomeAssistant | JSON REST payload | Yes, and uses epoch seconds rather than millis | Yes |
| ghc-db-manager | Reads and rewrites the native `.db` export zip | Yes | Yes |

Timestamp representation is inconsistent across these tools, with epoch millis, epoch seconds
and ISO 8601 all appearing, so the importer sniffs: a value above about 1e12 is milliseconds,
around 1e9 is seconds.

## 7. Browser parsing

The zip layer uses fflate rather than JSZip: 11.8 KB gzipped against 27.3 KB, and it can
stream from `file.stream()`, which matters for the Strava and Garmin archives. Neither
library supports encrypted zips, which does not matter here.

The trap is not the library. `File.arrayBuffer()` materialises one contiguous buffer while
the browser still holds the Blob, so peak memory approaches double the file size before any
work happens. Above roughly 50 MB the parse runs in a Web Worker so the tab stays responsive.

The SQLite layer uses sql.js, 314 KB gzipped, because it opens a database straight from a
`Uint8Array`, which is exactly what falls out of unzipping the single entry, with no OPFS or
VFS setup. Its limitation is holding the whole database in the WASM heap, making it a poor
fit above roughly 100 MB. One reported real-world export is about 20 MB zipped [3P], which
sits comfortably inside that; the figure is a single data point rather than a distribution,
and size scales with continuous heart-rate logging rather than with workout count.

## 8. Alternative feeds

| Format | Contents | Browser parsing |
|---|---|---|
| Strava bulk export | Zip with one GPX, FIT or TCX per activity plus `activities.csv` | Realistic, stream the zip and parse each small file |
| Garmin Connect export | Zip of original FIT files plus health time series, can reach several GB | A single activity file is trivial; the full archive needs streaming and a worker |
| Apple Health `export.xml` | One flat XML of `<Record>` elements, commonly 200 to 500 MB unzipped | DOM parsing fails past roughly 50 to 100 MB. Needs a chunked tokeniser |
| `.fit` | Binary tag-length-value, tens of KB to a few MB per activity | Yes, comfortably, from an ArrayBuffer |
| `.tcx`, `.gpx` | Shallow XML | Trivial, `DOMParser` is fine |

## 9. Sources

AOSP `platform/packages/modules/HealthFitness` branch main: the exportimport and
datatypehelpers directories, `ExerciseSessionType.java`, `ExerciseSegmentType.java`,
`Constants.java`, `DatabaseVersions.java`.

androidx branch androidx-main, `health/connect/connect-client`: the records and units
packages, `impl/platform/records/IntDefMappings.kt`.

Google Android Help page 15323271 on backup and restore.

Third-party corroboration: maciej-fafula/ghc-db-manager,
verybadsoldier/android-health-connect-data-explorer, AyraHikari/HealthConnect_to_HomeAssistant,
mmarca-tech/OpenVitals, CodyBontecou/obsidian-health-md.
