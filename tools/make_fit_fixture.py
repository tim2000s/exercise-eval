"""Write a valid FIT activity file, so the decoder is tested against the format rather than
against an assumption about it.

FIT is definition messages followed by data messages that refer back to them by a local type in
the range 0 to 15. The file carries a header, a body, and a CRC over both, and the header's own
data size field has to match the body exactly or a strict reader will refuse it.
"""

import struct
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

FIT_EPOCH_OFFSET = 631065600  # 31 Dec 1989 00:00:00 UTC, in unix seconds

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


def definition(local_type: int, global_num: int, fields: list[tuple[int, int]]) -> bytes:
    """fields is a list of (field number, base type)."""
    out = bytes([0x40 | local_type, 0x00, 0x00])          # header, reserved, little endian
    out += struct.pack("<HB", global_num, len(fields))
    for num, base in fields:
        out += bytes([num, SIZES[base], base])
    return out


def data(local_type: int, values: list[tuple[int, object]]) -> bytes:
    out = bytes([local_type])
    for base, value in values:
        if base == U32:
            out += struct.pack("<I", value)
        elif base == U16:
            out += struct.pack("<H", value)
        else:
            out += bytes([value])
    return out


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    # 3 August 2026, 18:00:00 UTC.
    start_unix = 1785780000
    start_fit = start_unix - FIT_EPOCH_OFFSET
    duration_s = 45 * 60

    body = b""

    # file_id: type 4 is an activity file.
    body += definition(0, 0, [(0, ENUM), (1, U16), (4, U32)])
    body += data(0, [(ENUM, 4), (U16, 1), (U32, start_fit)])

    # record: one per 10 seconds, with a heart rate ramp and accumulating distance.
    body += definition(1, 20, [(253, U32), (3, U8), (5, U32)])
    n = duration_s // 10
    for i in range(n):
        frac = i / n
        bpm = int(round(60 + 90 * min(1.0, frac / 0.1)))
        distance_cm = int(i * 10 * 3.0 * 100)   # 3 m/s
        body += data(1, [(U32, start_fit + i * 10), (U8, min(bpm, 200)), (U32, distance_cm)])

    # session summary.
    body += definition(2, 18, [(253, U32), (2, U32), (5, ENUM), (7, U32), (9, U32),
                               (11, U16), (16, U8), (17, U8)])
    body += data(2, [
        (U32, start_fit + duration_s),      # timestamp
        (U32, start_fit),                   # start_time
        (ENUM, 1),                          # sport: running
        (U32, duration_s * 1000),           # total_elapsed_time, thousandths of a second
        (U32, 8100 * 100),                  # total_distance, centimetres
        (U16, 520),                         # total_calories
        (U8, 148), (U8, 171),               # avg and max heart rate
    ])

    header = struct.pack("<BBHI4s", 12, 0x20, 2140, len(body), b".FIT")
    blob = header + body
    blob += struct.pack("<H", fit_crc(blob))

    path = OUT / "activity.fit"
    path.write_bytes(blob)
    print(f"{path} {len(blob)} bytes, {n} records")


if __name__ == "__main__":
    build()
