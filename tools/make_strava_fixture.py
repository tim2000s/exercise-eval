"""Build a synthetic Strava bulk export, shaped the way Strava actually ships one.

Three details of the real archive matter and are reproduced here. Individual activity files are
gzipped, so an entry is named 12345.fit.gz rather than 12345.fit. The summary activities.csv
uses a human date format rather than ISO 8601, and repeats several column names, which a naive
header map will collide on. And the archive carries a good deal that is not activity data at
all, which the importer has to skip without complaining.
"""

import csv
import gzip
import io
import struct
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
FIT_EPOCH_OFFSET = 631065600

ENUM, U8, U16, U32 = 0x00, 0x02, 0x84, 0x86
SIZES = {ENUM: 1, U8: 1, U16: 2, U32: 4}
CRC_TABLE = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
             0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]


def fit_crc(data: bytes) -> int:
    crc = 0
    for byte in data:
        for nibble in (byte & 0x0F, (byte >> 4) & 0x0F):
            tmp = CRC_TABLE[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ tmp ^ CRC_TABLE[nibble]
    return crc


def build_fit(start_unix: int, duration_s: int, sport: int, distance_m: int,
              kcal: int, avg_hr: int, max_hr: int) -> bytes:
    start_fit = start_unix - FIT_EPOCH_OFFSET

    def definition(local, global_num, fields):
        out = bytes([0x40 | local, 0x00, 0x00]) + struct.pack("<HB", global_num, len(fields))
        for num, base in fields:
            out += bytes([num, SIZES[base], base])
        return out

    def data(local, values):
        out = bytes([local])
        for base, value in values:
            out += struct.pack("<I", value) if base == U32 else (
                struct.pack("<H", value) if base == U16 else bytes([value]))
        return out

    body = definition(0, 0, [(0, ENUM), (1, U16), (4, U32)])
    body += data(0, [(ENUM, 4), (U16, 1), (U32, start_fit)])
    body += definition(1, 20, [(253, U32), (3, U8), (5, U32)])
    n = duration_s // 10
    for i in range(n):
        bpm = int(round(60 + (avg_hr - 60) * min(1.0, (i / n) / 0.1)))
        body += data(1, [(U32, start_fit + i * 10), (U8, min(bpm, 210)),
                         (U32, int(i * 10 * (distance_m / duration_s) * 100))])
    body += definition(2, 18, [(253, U32), (2, U32), (5, ENUM), (7, U32), (9, U32),
                               (11, U16), (16, U8), (17, U8)])
    body += data(2, [(U32, start_fit + duration_s), (U32, start_fit), (ENUM, sport),
                     (U32, duration_s * 1000), (U32, distance_m * 100), (U16, kcal),
                     (U8, avg_hr), (U8, max_hr)])
    header = struct.pack("<BBHI4s", 12, 0x20, 2140, len(body), b".FIT")
    blob = header + body
    return blob + struct.pack("<H", fit_crc(blob))


def build_gpx(start: datetime, minutes: int, name: str, sport: str) -> str:
    pts = []
    for i in range(minutes * 2):          # a point every 30 seconds
        t = start + timedelta(seconds=i * 30)
        lat = 51.5 + i * 0.00035
        pts.append(
            f'<trkpt lat="{lat:.6f}" lon="-0.120000"><ele>{10 + i % 25}</ele>'
            f'<time>{t.strftime("%Y-%m-%dT%H:%M:%SZ")}</time>'
            f'<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{130 + i % 20}</gpxtpx:hr>'
            f'</gpxtpx:TrackPointExtension></extensions></trkpt>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx creator="StravaGPX" version="1.1" xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">\n'
        f'<trk><name>{name}</name><type>{sport}</type><trkseg>\n'
        + "\n".join(pts) + "\n</trkseg></trk></gpx>\n")


def build_tcx(start: datetime, minutes: int, sport: str, distance_m: int, kcal: int) -> str:
    pts = []
    for i in range(minutes * 2):
        t = start + timedelta(seconds=i * 30)
        pts.append(
            f"<Trackpoint><Time>{t.strftime('%Y-%m-%dT%H:%M:%SZ')}</Time>"
            f"<HeartRateBpm><Value>{120 + i % 30}</Value></HeartRateBpm></Trackpoint>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">'
        f'<Activities><Activity Sport="{sport}"><Lap>'
        f"<Calories>{kcal}</Calories><DistanceMeters>{distance_m}</DistanceMeters>"
        "<Track>" + "".join(pts) + "</Track></Lap></Activity></Activities>"
        "</TrainingCenterDatabase>\n")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "strava_export.zip"

    # Strava prints dates as "3 Aug 2026, 17:00:00" in some locales and
    # "Aug 3, 2026, 5:00:00 PM" in others. The second is the one a naive parser trips on.
    specs = [
        # (id, filename, activity type, start, minutes, distance m, kcal, name)
        (9001, "activities/9001.fit.gz", "Ride",
         datetime(2026, 8, 2, 9, 0), 90, 42000, 980, "Sunday club ride"),
        (9002, "activities/9002.gpx", "Run",
         datetime(2026, 8, 3, 18, 0), 45, 8200, 520, "Evening run"),
        (9003, "activities/9003.tcx.gz", "Swim",
         datetime(2026, 8, 5, 7, 30), 40, 1800, 400, "Pool session"),
        (9004, "activities/9004.gpx.gz", "Walk",
         datetime(2026, 8, 7, 12, 0), 30, 2400, 110, "Walk to town"),
    ]

    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    # The real header repeats several names, which is worth reproducing.
    writer.writerow([
        "Activity ID", "Activity Date", "Activity Name", "Activity Type",
        "Activity Description", "Elapsed Time", "Distance", "Relative Effort", "Commute",
        "Activity Gear", "Filename", "Athlete Weight", "Bike Weight", "Elapsed Time",
        "Moving Time", "Distance", "Max Speed", "Average Speed", "Elevation Gain",
        "Max Heart Rate", "Average Heart Rate", "Calories",
    ])
    for aid, fname, atype, start, mins, dist, kcal, name in specs:
        writer.writerow([
            aid, start.strftime("%b %-d, %Y, %-I:%M:%S %p"), name, atype, "",
            mins * 60, dist / 1000, "", "false", "", fname, "", "",
            mins * 60, mins * 60, dist, "", "", "", 172, 148, kcal,
        ])

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("activities.csv", csv_buf.getvalue())

        for aid, fname, atype, start, mins, dist, kcal, name in specs:
            if fname.endswith(".fit.gz"):
                payload = gzip.compress(build_fit(
                    int(start.timestamp()), mins * 60, 2, dist, kcal, 132, 168))
            elif fname.endswith(".gpx.gz"):
                payload = gzip.compress(build_gpx(start, mins, name, atype.lower()).encode())
            elif fname.endswith(".tcx.gz"):
                payload = gzip.compress(build_tcx(start, mins, atype, dist, kcal).encode())
            elif fname.endswith(".gpx"):
                payload = build_gpx(start, mins, name, atype.lower()).encode()
            else:
                raise AssertionError(fname)
            z.writestr(fname, payload)

        # The rest of a real archive, which the importer has to skip without complaining.
        z.writestr("profile.csv", "First Name,Last Name\nA,Person\n")
        z.writestr("comments.csv", "Comment ID,Activity ID\n")
        z.writestr("followers.csv", "Follower,Status\n")
        z.writestr("media/9002-photo.jpg", b"\xff\xd8\xff\xe0not really a jpeg")
        z.writestr("clubs.json", '{"clubs": []}')

    print(f"{path} {path.stat().st_size / 1024:.0f} KiB, {len(specs)} activities")


if __name__ == "__main__":
    build()
