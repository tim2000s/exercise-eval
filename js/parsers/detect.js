// Work out what a dropped file actually is, from its bytes rather than its extension.
//
// Extensions lie. A Health Connect export renamed by the user, a Strava archive and a Garmin
// archive are all .zip; an exporter that writes JSON sometimes names it .txt. Sniffing the
// first few bytes is both more reliable and lets the importer say what it found, which is what
// the user needs when the answer is that the file is not what they thought.

const MAGIC = {
  zip: [0x50, 0x4b, 0x03, 0x04],
  zipEmpty: [0x50, 0x4b, 0x05, 0x06],
  gzip: [0x1f, 0x8b],
};

const startsWith = (bytes, sig) =>
  bytes.length >= sig.length && sig.every((b, i) => bytes[i] === b);

const textHead = (bytes, n = 4096) =>
  new TextDecoder('utf-8', { fatal: false }).decode(bytes.subarray(0, n));

/**
 * @returns {{kind: string, confident: boolean, detail: string}}
 *   kind is one of: health-connect-zip, archive-zip, sqlite, fit, gpx, tcx, apple-health-xml,
 *   csv, json, unknown
 */
export function detectFormat(bytes, filename = '') {
  const name = filename.toLowerCase();

  if (startsWith(bytes, MAGIC.zip) || startsWith(bytes, MAGIC.zipEmpty)) {
    // The Health Connect export holds exactly one entry with a known name. The entry name
    // appears in the local file header immediately after the 30-byte fixed part, so it can be
    // read without inflating anything.
    const head = textHead(bytes, 512);
    if (head.includes('health_connect_export.db')) {
      return { kind: 'health-connect-zip', confident: true,
        detail: 'A Health Connect export, holding one SQLite database.' };
    }
    if (head.includes('activities/') || head.includes('activities.csv')) {
      return { kind: 'archive-zip', confident: true,
        detail: 'A Strava bulk export, holding one file per activity.' };
    }
    return { kind: 'archive-zip', confident: false,
      detail: 'A zip archive. Its contents will be examined for anything recognisable.' };
  }

  // The SQLite header is a fixed 16-byte string, so a database extracted from the zip by hand
  // is recognised too.
  if (textHead(bytes, 16).startsWith('SQLite format 3')) {
    return { kind: 'sqlite', confident: true,
      detail: 'A SQLite database, most likely a Health Connect export already unzipped.' };
  }

  // FIT files carry .FIT at bytes 8 to 11, after a 12 or 14 byte header.
  if (bytes.length > 12 && String.fromCharCode(...bytes.subarray(8, 12)) === '.FIT') {
    return { kind: 'fit', confident: true, detail: 'A FIT activity file.' };
  }

  if (startsWith(bytes, MAGIC.gzip)) {
    return { kind: 'unknown', confident: false,
      detail: 'A gzip file. Decompress it first; this tool reads zip archives but not gzip.' };
  }

  const head = textHead(bytes).trimStart();

  if (head.startsWith('<')) {
    if (/<TrainingCenterDatabase/i.test(head)) {
      return { kind: 'tcx', confident: true, detail: 'A TCX activity file.' };
    }
    if (/<gpx/i.test(head)) {
      return { kind: 'gpx', confident: true, detail: 'A GPX track.' };
    }
    if (/<HealthData/i.test(head)) {
      return { kind: 'apple-health-xml', confident: true,
        detail: 'An Apple Health export. These are commonly 200 to 500 MB and are read in ' +
          'chunks rather than parsed as a document.' };
    }
    return { kind: 'unknown', confident: false, detail: 'An XML file of an unrecognised kind.' };
  }

  if (head.startsWith('{') || head.startsWith('[')) {
    return { kind: 'json', confident: true, detail: 'A JSON file.' };
  }

  // A CSV is recognised by a plausible header row rather than by commas alone, since a JSON
  // file with a leading blank line and a prose file both contain commas.
  const firstLine = head.split(/\r?\n/, 1)[0] || '';
  const delimiters = [',', ';', '\t', '|'].map((d) => firstLine.split(d).length - 1);
  if (Math.max(...delimiters) >= 2 && firstLine.length < 2000) {
    return { kind: 'csv', confident: false,
      detail: `A delimited text file with ${Math.max(...delimiters) + 1} columns in its first row.` };
  }

  return { kind: 'unknown', confident: false,
    detail: 'The file was not recognised. Supported formats are the Health Connect export ' +
      'zip, a SQLite database, CSV, JSON, FIT, TCX and GPX.' };
}
