// GPX and TCX readers.
//
// Both are shallow XML and DOMParser handles them without difficulty, unlike the Apple Health
// export, which is a single flat document commonly past 200 MB and needs a streaming approach.
//
// Neither format records insulin or carbohydrate. What they contribute is a session boundary
// and, in TCX, a heart rate series, which is what the intensity estimate needs.

import { decodeExerciseType, modalityFor } from './exercise-types.js';

const NS_TPX = 'http://www.garmin.com/xmlschemas/ActivityExtension/v2';

function parseXml(text, what) {
  const doc = new DOMParser().parseFromString(text, 'application/xml');
  const err = doc.querySelector('parsererror');
  if (err) throw new Error(`This ${what} file could not be parsed: ${err.textContent.trim()}`);
  return doc;
}

const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

/** Great-circle distance in metres, for GPX tracks that carry no distance field. */
function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/** TCX. One session per Activity element, with the sport attribute giving the type. */
export function parseTcx(text) {
  const doc = parseXml(text, 'TCX');
  const warnings = [];
  const sessions = [];

  for (const [i, act] of [...doc.getElementsByTagName('Activity')].entries()) {
    const sport = act.getAttribute('Sport') || '';
    const points = [];
    let distanceM = null;
    let calories = 0;

    for (const lap of act.getElementsByTagName('Lap')) {
      const cal = num(lap.getElementsByTagName('Calories')[0]?.textContent);
      if (cal) calories += cal;
      const d = num(lap.getElementsByTagName('DistanceMeters')[0]?.textContent);
      if (d) distanceM = (distanceM || 0) + d;
    }

    for (const tp of act.getElementsByTagName('Trackpoint')) {
      const t = Date.parse(tp.getElementsByTagName('Time')[0]?.textContent || '');
      if (!Number.isFinite(t)) continue;
      const bpm = num(tp.getElementsByTagName('Value')[0]?.textContent);
      points.push({ t, bpm });
    }
    if (!points.length) {
      warnings.push(`Activity ${i + 1} in this TCX file has no usable trackpoints.`);
      continue;
    }

    const start = points[0].t;
    const end = points[points.length - 1].t;
    const type = decodeExerciseType(sport, 'jetpack');
    sessions.push({
      id: `tcx-${i}`,
      start, end, durationMin: (end - start) / 60000,
      startOffsetSec: null, endOffsetSec: null,
      typeName: type.name, typeRaw: sport, typeKnown: type.known,
      modality: modalityFor(type.name),
      title: sport || null, notes: null, sourceApp: 'TCX file',
      distanceM, steps: null, elevationM: null,
      activeKcal: calories || null, totalKcal: null,
      hr: points.filter((p) => p.bpm).map((p) => ({ t: p.t, bpm: p.bpm })),
      speed: [], power: [], segments: [], laps: [],
    });
  }

  if (!sessions.length) warnings.push('No activities were found in this TCX file.');
  return { source: 'tcx', sessions, warnings, restingHr: [], vo2max: [], glucose: [],
    nutrition: [], sleep: [], meta: {} };
}

/** GPX. One session per track. Distance is computed from the points, since GPX has no field. */
export function parseGpx(text) {
  const doc = parseXml(text, 'GPX');
  const warnings = [];
  const sessions = [];

  for (const [i, trk] of [...doc.getElementsByTagName('trk')].entries()) {
    const pts = [];
    for (const p of trk.getElementsByTagName('trkpt')) {
      const t = Date.parse(p.getElementsByTagName('time')[0]?.textContent || '');
      if (!Number.isFinite(t)) continue;
      // Garmin and Strava write heart rate into the TrackPointExtension namespace.
      let bpm = null;
      for (const hr of p.getElementsByTagNameNS(NS_TPX, 'hr')) bpm = num(hr.textContent);
      if (bpm === null) {
        for (const hr of p.getElementsByTagName('gpxtpx:hr')) bpm = num(hr.textContent);
      }
      pts.push({
        t,
        lat: num(p.getAttribute('lat')),
        lon: num(p.getAttribute('lon')),
        ele: num(p.getElementsByTagName('ele')[0]?.textContent),
        bpm,
      });
    }
    if (pts.length < 2) {
      warnings.push(`Track ${i + 1} in this GPX file has too few timed points to use.`);
      continue;
    }

    let distanceM = 0;
    let elevationM = 0;
    for (let j = 1; j < pts.length; j++) {
      const a = pts[j - 1];
      const b = pts[j];
      if (a.lat !== null && b.lat !== null) distanceM += haversine(a.lat, a.lon, b.lat, b.lon);
      if (a.ele !== null && b.ele !== null && b.ele > a.ele) elevationM += b.ele - a.ele;
    }

    const name = trk.getElementsByTagName('name')[0]?.textContent || null;
    const type = decodeExerciseType(
      trk.getElementsByTagName('type')[0]?.textContent || '', 'jetpack');

    sessions.push({
      id: `gpx-${i}`,
      start: pts[0].t, end: pts[pts.length - 1].t,
      durationMin: (pts[pts.length - 1].t - pts[0].t) / 60000,
      startOffsetSec: null, endOffsetSec: null,
      typeName: type.name, typeRaw: type.raw, typeKnown: type.known,
      modality: modalityFor(type.name),
      title: name, notes: null, sourceApp: 'GPX file',
      distanceM: Math.round(distanceM), steps: null,
      elevationM: Math.round(elevationM),
      activeKcal: null, totalKcal: null,
      hr: pts.filter((p) => p.bpm).map((p) => ({ t: p.t, bpm: p.bpm })),
      speed: [], power: [], segments: [], laps: [],
    });
  }

  if (!sessions.length) warnings.push('No timed tracks were found in this GPX file.');
  const noHr = sessions.filter((s) => !s.hr.length).length;
  if (noHr) {
    warnings.push(
      `${noHr} of ${sessions.length} tracks carry no heart rate. GPX records it only as a ` +
        'vendor extension, so intensity for those sessions comes from the activity label alone.',
    );
  }
  return { source: 'gpx', sessions, warnings, restingHr: [], vo2max: [], glucose: [],
    nutrition: [], sleep: [], meta: {} };
}
