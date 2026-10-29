"""Minimal ASAR reader/writer for the Freebuff Desktop shell.

Electron's asar layout:
    4 x uint32 little-endian pickle prefix
    N bytes of JSON header (N = 4th uint32)
    file data, offsets in the header are relative to the end of the header

Only what this repo needs: read the tree, read one file, and rewrite the
header while keeping the data block byte-identical (offsets shifted by the
header-length delta).
"""

from __future__ import annotations

import hashlib
import json
import struct


def load(path: str):
    blob = open(path, "rb").read()
    prefix = struct.unpack("<4I", blob[:16])
    header_len = prefix[3]
    header = json.loads(blob[16:16 + header_len])
    data = blob[16 + header_len:]
    return header, data


def entry(header: dict, rel: str) -> dict:
    node = header["files"]
    for part in rel.split("/"):
        node = node[part]
        if "files" in node:
            node = node["files"]
    return node


def read_file(path: str, rel: str) -> bytes:
    header, data = load(path)
    e = entry(header, rel)
    off, size = int(e["offset"]), int(e["size"])
    return data[off:off + size]


def walk(node: dict, prefix: str = ""):
    for name, value in node.get("files", {}).items():
        rel = f"{prefix}/{name}" if prefix else name
        if "files" in value:
            yield from walk(value, rel)
        else:
            yield rel, value


def pack_like(path: str, out_path: str, header: dict, data: bytes) -> None:
    """Write `header` + `data` with offsets shifted by the header delta."""
    raw = json.dumps(header, separators=(",", ":")).encode("utf-8")
    # pad to a 4-byte boundary so file data stays aligned
    pad = (-len(raw)) % 4
    raw += b" " * pad
    old_len = struct.unpack("<4I", open(path, "rb").read(16))[3]
    delta = len(raw) - old_len
    if delta:
        for _rel, e in walk(header):
            if "offset" in e:
                e["offset"] = str(int(e["offset"]) + delta)
        raw = json.dumps(header, separators=(",", ":")).encode("utf-8")
        pad = (-len(raw)) % 4
        raw += b" " * pad
        # delta must be recomputed only once: offsets were shifted from the
        # original values, so re-serialising must not change the length again
    prefix = struct.pack("<4I", 4, len(raw) + 4, len(raw), len(raw))
    with open(out_path, "wb") as fh:
        fh.write(prefix)
        fh.write(raw)
        fh.write(data)


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()
