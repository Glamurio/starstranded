"""Stable seed mixing shared by every deterministic generator (worldgen, planet catalogue, naming)."""
from __future__ import annotations

import hashlib
import struct


def mix_seed(*values: int) -> int:
    """A stable 63-bit seed from ints (negative ones fine), identical across processes and platforms."""
    digest = hashlib.blake2b(struct.pack(f"<{len(values)}q", *values), digest_size=8).digest()
    return int.from_bytes(digest, "little") >> 1
