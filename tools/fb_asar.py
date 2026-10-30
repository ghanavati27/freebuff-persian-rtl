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
    # The header block is padded so the data section starts on a 4-byte
    # boundary; the offsets are relative to that padded start, not to the JSON.
    pad = (-(16 + header_len)) % 4
    data = blob[16 + header_len + pad:]
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


def _encode_header(header: dict) -> bytes:
    """Serialise the header and pad it so the data block starts 4-byte aligned."""
    raw = json.dumps(header, separators=(",", ":")).encode("utf-8")
    pad = (-(16 + len(raw))) % 4
    return raw + b" " * pad


def pack_like(path: str, out_path: str, header: dict, data: bytes) -> None:
    """Write `header` + `data`, moving offsets by however far the data block moved."""
    old_len = struct.unpack("<4I", open(path, "rb").read(16))[3]
    old_base = 16 + old_len + (-(16 + old_len)) % 4
    original = {}
    for _rel, e in walk(header):
        if "offset" in e:
            original[id(e)] = int(e["offset"])
    # Shifting an offset can change its digit count, which changes the header
    # length, which changes the shift. Recompute from the originals until it
    # settles (two passes in practice).
    for _ in range(5):
        raw = _encode_header(header)
        delta = (16 + len(raw)) - old_base
        if delta == 0:
            break
        for _rel, e in walk(header):
            if id(e) in original:
                e["offset"] = str(original[id(e)] + delta)
    raw = _encode_header(header)
    prefix = struct.pack("<4I", 4, len(raw) + 4, len(raw), len(raw))
    with open(out_path, "wb") as fh:
        fh.write(prefix)
        fh.write(raw)
        fh.write(data)


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()
