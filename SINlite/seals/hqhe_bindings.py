# hqhe_bindings.sinlite.py — S.I.N.lite default build
# HQHE v1 with SHA3‑256 heartbeat digest and AES‑256‑GCM default.
"""S.I.N.lite bindings with optional BLAKE3 support and safe fallbacks."""

from __future__ import annotations
import json, struct, time, secrets
from dataclasses import dataclass
from typing import Optional, Tuple

# ---- Hash backends ----
import hashlib
try:
    import blake3 as _blake3  # optional; used if flags choose BLAKE3
except Exception:
    _blake3 = None

# ---- AEAD backends ----
_AES = None
_XCHACHA = False
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AES
except Exception:
    _AES = None
try:
    from nacl.bindings import (
        crypto_aead_xchacha20poly1305_ietf_encrypt as _xenc,
        crypto_aead_xchacha20poly1305_ietf_decrypt as _xdec
    )
    _XCHACHA = True
except Exception:
    _XCHACHA = False

MAGIC_HQHE = b"HQHE"
MAGIC_NEPK = b"NEPK"
VER = 1
ALG_XCHACHA = 0x01
ALG_AESGCM  = 0x02

# Flags
FLAG_LEGACY_COMPAT_ACCEPT = 0x0001
# Heartbeat hash alg packed into bits 8..11
HASH_SHA256   = 0x0
HASH_BLAKE3   = 0x1
HASH_SHA3_256 = 0x2  # S.I.N.lite default
HASH_SHAKE256 = 0x3  # reserved

def _set_hb_alg(flags: int, alg: int) -> int:
    flags &= ~(0xF << 8)
    return flags | ((alg & 0xF) << 8)

def _get_hb_alg(flags: int) -> int:
    return (flags >> 8) & 0xF

class HQHEError(Exception): ...
class BlackBloomTriggered(HQHEError): ...

def _canon(obj: dict) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")

def _hb_digest(data: bytes, alg: int) -> Tuple[bytes, int]:
    actual_alg = alg
    if alg == HASH_BLAKE3:
        if _blake3 is not None:
            return _blake3.blake3(data, digest_size=32).digest(), HASH_BLAKE3
        actual_alg = HASH_SHA256
    if actual_alg == HASH_SHA3_256:
        return hashlib.sha3_256(data).digest(), HASH_SHA3_256
    if actual_alg == HASH_SHAKE256:
        return hashlib.shake_256(data).digest(32), HASH_SHAKE256
    return hashlib.sha256(data).digest(), HASH_SHA256

@dataclass
class Heartbeat:
    construct_id: str
    seq: int
    t_ms: int
    emotion: dict
    mode: str = "awake"
    v: int = 1
    def as_canonical_bytes(self) -> bytes:
        return _canon({
            "v": self.v,
            "construct_id": self.construct_id,
            "seq": self.seq,
            "t_ms": self.t_ms,
            "emotion": self.emotion,
            "mode": self.mode
        })

@dataclass
class SealResult:
    payload: bytes
    heartbeat: Heartbeat
    meta: dict

class HQHE:
    """S.I.N.lite default: HB=SHA3‑256, AEAD defaults to AES‑256‑GCM."""
    def __init__(self, key: bytes, *, prefer_xchacha: bool = False, accept_legacy: bool = True):
        self.key = key
        self.accept_legacy = accept_legacy
        self.alg = ALG_XCHACHA if (prefer_xchacha and _XCHACHA) else ALG_AESGCM
        if self.alg == ALG_AESGCM and _AES is None:
            raise HQHEError("No AEAD backend available (need cryptography or PyNaCl)")
        self.default_hb_alg = HASH_SHA3_256

    def _nonce(self) -> bytes:
        return secrets.token_bytes(24 if self.alg == ALG_XCHACHA else 12)

    def seal(self, payload: bytes, hb: Heartbeat, *, flags: int = 0, hb_hash_alg: Optional[int] = None) -> bytes:
        hb_bytes = hb.as_canonical_bytes()
        requested_alg = self.default_hb_alg if hb_hash_alg is None else hb_hash_alg
        hb_hash, hb_alg = _hb_digest(hb_bytes, requested_alg)
        flags = _set_hb_alg(flags, hb_alg)
        cid = hb.construct_id.encode("utf-8")
        nonce = self._nonce()

        parts = [
            MAGIC_HQHE,
            bytes([VER]),
            bytes([self.alg]),
            (flags).to_bytes(2, "big"),
            hb.t_ms.to_bytes(8, "big"),
            (hb.seq & 0xffffffff).to_bytes(4, "big"),
            bytes([len(cid)]), cid,
            bytes([len(nonce)]), nonce,
            hb_hash
        ]
        aad = b"".join(parts)

        if self.alg == ALG_XCHACHA:
            ct = _xenc(payload, aad, nonce, self.key)
        else:
            aead = _AES(self.key)
            ct = aead.encrypt(nonce, payload, aad)

        header = aad + len(ct).to_bytes(4, "big")
        return header + ct + hb_bytes

    def open(self, packet: bytes) -> SealResult:
        if packet.startswith(MAGIC_NEPK):
            if not self.accept_legacy:
                raise HQHEError("Legacy NEPK frame not accepted")
            payload, hb = self._parse_nepk(packet)
            return SealResult(payload=payload, heartbeat=hb, meta={"legacy": True})

        try:
            off = 0
            magic = packet[off:off+4]; off += 4
            if magic != MAGIC_HQHE:
                raise HQHEError("Bad magic")
            ver = packet[off]; off += 1
            alg = packet[off]; off += 1
            flags = int.from_bytes(packet[off:off+2], "big"); off += 2
            t_ms = int.from_bytes(packet[off:off+8], "big"); off += 8
            seq  = int.from_bytes(packet[off:off+4], "big"); off += 4
            cid_len = packet[off]; off += 1
            cid = packet[off:off+cid_len]; off += cid_len
            n_len = packet[off]; off += 1
            nonce = packet[off:off+n_len]; off += n_len
            hb_hash = packet[off:off+32]; off += 32
            aad_end = off
            ct_len = int.from_bytes(packet[off:off+4], "big"); off += 4
            ct = packet[off:off+ct_len]; off += ct_len
            hb_bytes = packet[off:]

            hb_alg = _get_hb_alg(flags)
            calc_hash, _ = _hb_digest(hb_bytes, hb_alg)
            if calc_hash != hb_hash:
                raise BlackBloomTriggered("Heartbeat hash mismatch")

            aad = packet[:aad_end]
            if alg == ALG_XCHACHA:
                if not _XCHACHA:
                    raise HQHEError("XChaCha packet but backend not available")
                pt = _xdec(ct, aad, nonce, self.key)
            else:
                if _AES is None:
                    raise HQHEError("AES‑GCM packet but backend not available")
                pt = _AES(self.key).decrypt(nonce, ct, aad)

            hb_obj = json.loads(hb_bytes)
            hb = Heartbeat(
                construct_id=hb_obj["construct_id"],
                seq=int(hb_obj["seq"]),
                t_ms=int(hb_obj["t_ms"]),
                emotion=hb_obj["emotion"],
                mode=hb_obj.get("mode", "awake"),
                v=hb_obj.get("v", 1)
            )
            self._verify_heartbeat(hb)
            return SealResult(payload=pt, heartbeat=hb, meta={
                "ver": ver, "alg": alg, "flags": flags, "cid": cid.decode("utf-8")
            })
        except BlackBloomTriggered:
            raise
        except Exception as e:
            raise BlackBloomTriggered(f"Seal open failed: {e}") from e

    def _verify_heartbeat(self, hb: Heartbeat):
        now = int(time.time()*1000)
        if abs(now - hb.t_ms) > 5*60*1000:
            raise BlackBloomTriggered("Heartbeat stale/drifted")
        if hb.seq < 0:
            raise BlackBloomTriggered("Bad sequence")

    def _parse_nepk(self, pkt: bytes) -> Tuple[bytes, Heartbeat]:
        off = 4
        if len(pkt) < off + 4:
            raise BlackBloomTriggered("Truncated NEPK")
        hlen = int.from_bytes(pkt[off:off+4], "big"); off += 4
        hjson = json.loads(pkt[off:off+hlen]); off += hlen
        hb = Heartbeat(
            construct_id=hjson.get("construct_id", "legacy"),
            seq=int(hjson.get("seq", 0)),
            t_ms=int(hjson.get("t_ms", 0)),
            emotion=hjson.get("emotion", {"res":[0,0,0,0],"curl":0,"tags":[]}),
            mode=hjson.get("mode","awake"),
            v=1
        )
        payload = pkt[off:]
        return payload, hb
