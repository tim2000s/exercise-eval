// FIT activity file decoder.
//
// FIT is a binary format of definition messages followed by data messages that refer back to
// them. A definition says which fields a later data message will carry, in what order, at what
// size and in what base type; a data message is then just packed values with no self-describing
// structure at all. Reading one therefore means keeping a table of the sixteen possible local
// message slots and rewriting entries as new definitions arrive.
//
// Only the messages this tool uses are interpreted: file_id, session, lap, record and event.
// Everything else is skipped by the length the definition gives, which is what makes it safe to
// ignore the several hundred message types not handled here.
//
// Written out rather than pulled from a library because the subset needed is small, the format
// is stable, and a decoder that reports what it skipped is more useful here than one that
// silently returns an empty list.

import { decodeExerciseType, modalityFor } from './exercise-types.js';

/** FIT epoch is 31 December 1989 00:00:00 UTC, in seconds. */
const FIT_EPOCH_MS = 631065600000;

const GLOBAL = { FILE_ID: 0, SESSION: 18, LAP: 19, RECORD: 20, EVENT: 21, ACTIVITY: 34 };

// [size in bytes, reader name, invalid value]. A field equal to its invalid value is absent,
// which is how FIT represents a missing reading rather than omitting the field.
const BASE_TYPES = {
  0x00: [1, 'u8', 0xff],        // enum
  0x01: [1, 'i8', 0x7f],
  0x02: [1, 'u8', 0xff],
  0x83: [2, 'i16', 0x7fff],
  0x84: [2, 'u16', 0xffff],
  0x85: [4, 'i32', 0x7fffffff],
  0x86: [4, 'u32', 0xffffffff],
  0x07: [1, 'string', 0x00],
  0x88: [4, 'f32', 0xffffffff],
  0x89: [8, 'f64', null],
  0x0a: [1, 'u8', 0x00],        // uint8z
  0x8b: [2, 'u16', 0x00],
  0x8c: [4, 'u32', 0x00],
  0x0d: [1, 'u8', 0xff],        // byte
  0x8e: [8, 'i64', null],
  0x8f: [8, 'u64', null],
  0x90: [8, 'u64', 0x00],
};

/** Sport enum, the values this tool can map onto a Health Connect exercise type. */
const SPORT = {
  0: 'OTHER_WORKOUT', 1: 'RUNNING', 2: 'BIKING', 4: 'ELLIPTICAL', 5: 'SWIMMING_POOL',
  6: 'BASKETBALL', 7: 'SOCCER', 8: 'TENNIS', 9: 'FOOTBALL_AMERICAN', 10: 'STRENGTH_TRAINING',
  11: 'WALKING', 12: 'SKIING', 13: 'SKIING', 14: 'SNOWBOARDING', 15: 'ROWING',
  16: 'ROCK_CLIMBING', 17: 'HIKING', 19: 'PADDLING', 21: 'BIKING', 25: 'GOLF',
  27: 'OTHER_WORKOUT', 30: 'SKATING', 31: 'ROCK_CLIMBING', 32: 'SAILING', 33: 'ICE_SKATING',
  35: 'SNOWSHOEING', 37: 'PADDLING', 38: 'SURFING', 41: 'PADDLING', 43: 'SAILING',
  47: 'BOXING', 48: 'ROCK_CLIMBING', 53: 'SCUBA_DIVING',
};

/** Field numbers, per message type, for the fields this tool reads. */
const FIELDS = {
  [GLOBAL.SESSION]: {
    253: 'timestamp', 2: 'startTime', 5: 'sport', 6: 'subSport', 7: 'totalElapsedTime',
    8: 'totalTimerTime', 9: 'totalDistance', 11: 'totalCalories', 13: 'totalAscent',
    16: 'avgHeartRate', 17: 'maxHeartRate', 14: 'avgSpeed', 15: 'maxSpeed',
  },
  [GLOBAL.RECORD]: {
    253: 'timestamp', 3: 'heartRate', 4: 'cadence', 5: 'distance', 6: 'speed', 7: 'power',
    2: 'altitude', 73: 'enhancedSpeed', 78: 'enhancedAltitude',
  },
  [GLOBAL.LAP]: {
    253: 'timestamp', 2: 'startTime', 7: 'totalElapsedTime', 9: 'totalDistance',
  },
  [GLOBAL.FILE_ID]: { 0: 'type', 1: 'manufacturer', 4: 'timeCreated' },
};

class Reader {
  constructor(bytes) {
    this.view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    this.bytes = bytes;
    this.pos = 0;
  }

  get remaining() { return this.bytes.length - this.pos; }

  read(kind, size, littleEndian) {
    const v = this.view;
    const p = this.pos;
    this.pos += size;
    switch (kind) {
      case 'u8': return v.getUint8(p);
      case 'i8': return v.getInt8(p);
      case 'u16': return v.getUint16(p, littleEndian);
      case 'i16': return v.getInt16(p, littleEndian);
      case 'u32': return v.getUint32(p, littleEndian);
      case 'i32': return v.getInt32(p, littleEndian);
      case 'f32': return v.getFloat32(p, littleEndian);
      case 'f64': return v.getFloat64(p, littleEndian);
      case 'u64': case 'i64': {
        const big = kind === 'u64' ? v.getBigUint64(p, littleEndian) : v.getBigInt64(p, littleEndian);
        return Number(big);
      }
      case 'string': {
        const raw = this.bytes.subarray(p, p + size);
        const end = raw.indexOf(0);
        return new TextDecoder().decode(end === -1 ? raw : raw.subarray(0, end));
      }
      default:
        return null;
    }
  }
}

function readField(reader, baseType, size, littleEndian) {
  const spec = BASE_TYPES[baseType] ?? BASE_TYPES[baseType & 0x1f] ?? null;
  if (!spec) {
    reader.pos += size;
    return null;
  }
  const [unitSize, kind, invalid] = spec;

  if (kind === 'string') {
    return reader.read('string', size, littleEndian);
  }
  // A field wider than one unit is an array. Only the first element is used, since none of the
  // fields this tool reads are genuinely arrays and taking the first is harmless if one is.
  const count = Math.max(1, Math.floor(size / unitSize));
  let first = null;
  for (let i = 0; i < count; i++) {
    const v = reader.read(kind, unitSize, littleEndian);
    if (i === 0) first = v;
  }
  reader.pos += size - count * unitSize; // any padding the writer added
  return invalid !== null && first === invalid ? null : first;
}

/**
 * Decode a FIT file into the tool's session shape.
 *
 * @param {Uint8Array} bytes
 */
export function parseFit(bytes) {
  const warnings = [];
  if (bytes.length < 14) throw new Error('This file is too short to be a FIT file.');

  const headerSize = bytes[0];
  if (String.fromCharCode(...bytes.subarray(8, 12)) !== '.FIT') {
    throw new Error('This file does not carry the .FIT signature at bytes 8 to 11.');
  }
  const dataSize = new DataView(bytes.buffer, bytes.byteOffset).getUint32(4, true);
  const dataEnd = Math.min(bytes.length, headerSize + dataSize);

  // The header states how many bytes of message data follow. A file shorter than that is
  // truncated even when it happens to end on a message boundary, in which case nothing further
  // down would notice, so the comparison is made here where the declared length is available.
  // Two trailing CRC bytes are expected beyond the data, hence the small tolerance.
  if (bytes.length < headerSize + dataSize) {
    warnings.push(
      `The file is truncated: its header declares ${dataSize} bytes of data but only ` +
        `${Math.max(0, bytes.length - headerSize)} are present. Everything up to the cut is ` +
        'reported.',
    );
  }

  const reader = new Reader(bytes);
  reader.pos = headerSize;

  const definitions = new Map();   // local message type -> definition
  const sessions = [];
  const records = [];
  const laps = [];
  let fileType = null;
  let skipped = 0;

  while (reader.pos < dataEnd) {
    const header = reader.read('u8', 1, true);
    let localType;
    let isDefinition = false;
    let hasDeveloper = false;

    if (header & 0x80) {
      // Compressed timestamp header. The local type lives in bits 5 and 6, and the low five
      // bits are a time offset that only matters for messages this tool does not use.
      localType = (header >> 5) & 0x03;
    } else {
      isDefinition = Boolean(header & 0x40);
      hasDeveloper = Boolean(header & 0x20);
      localType = header & 0x0f;
    }

    if (isDefinition) {
      if (reader.remaining < 5) {
        warnings.push(
          'The file ends part-way through a definition message, so it is truncated. Everything ' +
            'decoded before that point is reported.',
        );
        break;
      }
      reader.read('u8', 1, true);                       // reserved
      const littleEndian = reader.read('u8', 1, true) === 0;
      const globalNum = reader.read('u16', 2, littleEndian);
      const fieldCount = reader.read('u8', 1, true);
      if (reader.remaining < fieldCount * 3) {
        warnings.push('The file ends inside a definition message field list, so it is truncated.');
        break;
      }
      const fields = [];
      for (let i = 0; i < fieldCount; i++) {
        fields.push({
          num: reader.read('u8', 1, true),
          size: reader.read('u8', 1, true),
          baseType: reader.read('u8', 1, true),
        });
      }
      if (hasDeveloper) {
        const devCount = reader.read('u8', 1, true);
        for (let i = 0; i < devCount; i++) {
          const num = reader.read('u8', 1, true);
          const size = reader.read('u8', 1, true);
          reader.read('u8', 1, true);                   // developer data index
          // Developer fields are not interpreted, but their width has to be known so that the
          // data message can be walked past correctly.
          fields.push({ num: -1, size, baseType: 0x0d, developer: true });
        }
      }
      definitions.set(localType, { globalNum, littleEndian, fields });
      continue;
    }

    const def = definitions.get(localType);
    if (!def) {
      // A data message with no definition means the stream is out of step, and continuing
      // would read garbage as though it were data.
      warnings.push(
        `A data message referred to local type ${localType}, which has no definition. The file ` +
          'is truncated or was written incorrectly, so reading stopped here.',
      );
      break;
    }

    const messageBytes = def.fields.reduce((a, f) => a + f.size, 0);
    if (reader.remaining < messageBytes) {
      warnings.push(
        `The file ends part-way through a data message: ${messageBytes} bytes were expected and ` +
          `${reader.remaining} remain. It is truncated, and everything decoded before that ` +
          'point is reported.',
      );
      break;
    }

    const names = FIELDS[def.globalNum];
    const values = {};
    for (const f of def.fields) {
      const v = readField(reader, f.baseType, f.size, def.littleEndian);
      if (names && !f.developer && names[f.num] !== undefined && v !== null) {
        values[names[f.num]] = v;
      }
    }
    if (!names) { skipped++; continue; }

    if (def.globalNum === GLOBAL.FILE_ID) fileType = values.type ?? fileType;
    else if (def.globalNum === GLOBAL.SESSION) sessions.push(values);
    else if (def.globalNum === GLOBAL.RECORD) records.push(values);
    else if (def.globalNum === GLOBAL.LAP) laps.push(values);
  }

  if (skipped) {
    warnings.push(`${skipped} messages of types this tool does not read were skipped.`);
  }
  // 4 is the activity file type. Anything else is a monitoring, workout or settings file, and
  // will contain no sessions.
  if (fileType !== null && fileType !== 4) {
    warnings.push(
      `This is FIT file type ${fileType} rather than an activity file, so it may hold no ` +
        'exercise sessions.',
    );
  }

  const toMs = (fitSeconds) =>
    Number.isFinite(fitSeconds) ? FIT_EPOCH_MS + fitSeconds * 1000 : null;

  const hrSeries = records
    .filter((r) => r.heartRate && r.timestamp)
    .map((r) => ({ t: toMs(r.timestamp), bpm: r.heartRate }));

  const out = sessions.map((s, i) => {
    const start = toMs(s.startTime) ?? (hrSeries.length ? hrSeries[0].t : null);
    const elapsed = s.totalElapsedTime ?? s.totalTimerTime;
    // Elapsed time is stored in units of 1/1000 s.
    const end = start !== null && Number.isFinite(elapsed)
      ? start + elapsed
      : toMs(s.timestamp);
    if (start === null || end === null || end <= start) return null;

    const name = SPORT[s.sport] || 'OTHER_WORKOUT';
    const type = decodeExerciseType(name, 'jetpack');

    return {
      id: `fit-${i}`,
      start, end, durationMin: (end - start) / 60000,
      startOffsetSec: null, endOffsetSec: null,
      typeName: type.name, typeRaw: s.sport, typeKnown: Boolean(SPORT[s.sport]),
      modality: modalityFor(type.name),
      title: null, notes: null, sourceApp: 'FIT file',
      // Distance is stored in centimetres, speed in mm/s.
      distanceM: Number.isFinite(s.totalDistance) ? s.totalDistance / 100 : null,
      steps: null,
      elevationM: Number.isFinite(s.totalAscent) ? s.totalAscent : null,
      activeKcal: Number.isFinite(s.totalCalories) ? s.totalCalories : null,
      totalKcal: null,
      avgHr: s.avgHeartRate ?? null,
      maxHr: s.maxHeartRate ?? null,
      hr: hrSeries.filter((p) => p.t >= start && p.t <= end),
      speed: [], power: [],
      segments: [],
      laps: laps
        .filter((l) => toMs(l.startTime) >= start && toMs(l.startTime) <= end)
        .map((l) => ({ start: toMs(l.startTime), end: toMs(l.timestamp),
                       lengthM: Number.isFinite(l.totalDistance) ? l.totalDistance / 100 : null })),
    };
  }).filter(Boolean);

  if (!out.length && records.length) {
    // Some watches write records without a session summary. The record stream still bounds a
    // session, so one is synthesised rather than reporting nothing.
    const timed = records.filter((r) => r.timestamp).map((r) => toMs(r.timestamp));
    if (timed.length > 1) {
      warnings.push(
        'This FIT file has no session summary message, so the session boundaries were taken ' +
          'from the first and last data records and the activity type is unknown.',
      );
      out.push({
        id: 'fit-derived', start: Math.min(...timed), end: Math.max(...timed),
        durationMin: (Math.max(...timed) - Math.min(...timed)) / 60000,
        startOffsetSec: null, endOffsetSec: null,
        typeName: 'UNKNOWN', typeRaw: null, typeKnown: false, modality: 'unknown',
        title: null, notes: null, sourceApp: 'FIT file',
        distanceM: null, steps: null, elevationM: null, activeKcal: null, totalKcal: null,
        hr: hrSeries, speed: [], power: [], segments: [], laps: [],
      });
    }
  }
  if (!out.length) warnings.push('No exercise sessions were found in this FIT file.');

  return { source: 'fit', sessions: out, warnings, restingHr: [], vo2max: [], glucose: [],
    nutrition: [], sleep: [], meta: { records: records.length, fileType } };
}
