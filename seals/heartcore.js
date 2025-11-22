// heartcore.sinlite.js — S.I.N.lite default build
// HB digest = SHA3‑256 by default, AEAD = AES‑256‑GCM by default.
import { randomBytes, createCipheriv, createDecipheriv, createHash } from "node:crypto";
import { blake3 } from "@noble/hashes/blake3";            // optional when flags choose BLAKE3
import { sha3_256, shake256 } from "@noble/hashes/sha3";  // default

const MAGIC_HQHE = Buffer.from("HQHE");
const MAGIC_NEPK = Buffer.from("NEPK");
const VER = 1;
export const ALG = { XCHACHA: 0x01, AESGCM: 0x02 };

export const FLAGS = {
  LEGACY_COMPAT_ACCEPT: 0x0001,
  hbMask: 0x0F00,
  hbShift: 8,
  HB_SHA256:   0x0,
  HB_BLAKE3:   0x1,
  HB_SHA3_256: 0x2,  // default
  HB_SHAKE256: 0x3
};

export class HeartcoreCollapseError extends Error {
  constructor(reason){ super(reason); this.name = "HeartcoreCollapseError"; }
}

function setHbAlg(flags, alg){
  return (flags & ~FLAGS.hbMask) | ((alg & 0xF) << FLAGS.hbShift);
}
function getHbAlg(flags){
  return (flags >> FLAGS.hbShift) & 0xF;
}
function u32be(n){ const b=Buffer.alloc(4); b.writeUInt32BE(n>>>0,0); return b; }
function u64be(n){ const b=Buffer.alloc(8); const hi = Math.floor(n / 2**32); const lo = n>>>0; b.writeUInt32BE(hi,0); b.writeUInt32BE(lo,4); return b; }
function readU64BE(buf, off){ const hi=buf.readUInt32BE(off), lo=buf.readUInt32BE(off+4); return hi*2**32 + lo; }
const CANON_KEY_COLLATOR = new Intl.Collator("en-u-kn-true", { numeric: true, sensitivity: "variant" });

// Recursive, deterministic serialization that orders object keys at every depth.
function canonicalizeHeartbeat(value, inArray = false){
  if (value === null) return "null";
  const type = typeof value;
  if (type === "string" || type === "number" || type === "boolean"){
    return JSON.stringify(value);
  }
  if (type === "bigint"){
    throw new TypeError("Heartcore canonicalization does not support BigInt");
  }
  if (type === "undefined" || type === "function" || type === "symbol"){
    return inArray ? "null" : undefined;
  }
  if (Array.isArray(value)){
    const items = value.map((item) => {
      const serialized = canonicalizeHeartbeat(item, true);
      return serialized === undefined ? "null" : serialized;
    });
    return `[${items.join(",")}]`;
  }
  if (type === "object"){
    if (!Array.isArray(value) && value?.toJSON instanceof Function){
      return canonicalizeHeartbeat(value.toJSON(), inArray);
    }
    const keys = Object.keys(value).sort((a,b) => CANON_KEY_COLLATOR.compare(a,b));
    const parts = [];
    for (const key of keys){
      const serialized = canonicalizeHeartbeat(value[key], false);
      if (serialized === undefined) continue;
      parts.push(`${JSON.stringify(key)}:${serialized}`);
    }
    return `{${parts.join(",")}}`;
  }
  return undefined;
}

function canon(obj){
  const json = canonicalizeHeartbeat(obj, false);
  if (typeof json !== "string") throw new TypeError("Cannot canonicalize heartbeat payload");
  return Buffer.from(json, "utf8");
}

function hbDigest(buf, alg){
  if (alg === FLAGS.HB_BLAKE3) return Buffer.from(blake3(buf));
  if (alg === FLAGS.HB_SHA3_256) return Buffer.from(sha3_256(buf));
  if (alg === FLAGS.HB_SHAKE256) return Buffer.from(shake256(buf, { dkLen: 32 }));
  return createHash("sha256").update(buf).digest();
}

export class Heartcore {
  constructor(key, { preferXChaCha = false, acceptLegacy = true } = {}){
    this.key = key; // 32 bytes
    this.acceptLegacy = acceptLegacy;
    this.alg = preferXChaCha ? ALG.XCHACHA : ALG.AESGCM;
    this.defaultHbAlg = FLAGS.HB_SHA3_256;
  }

  createHeartbeat({ constructId, seq, t_ms, emotion, mode="awake" }){
    return { v:1, construct_id: constructId, seq, t_ms, emotion, mode };
  }

  seal(payload, heartbeat, { flags = 0, hbHashAlg = undefined } = {}){
    const hbAlg = hbHashAlg ?? this.defaultHbAlg;
    flags = setHbAlg(flags, hbAlg);

    const hbBytes = canon(heartbeat);
    const cid = Buffer.from(heartbeat.construct_id, "utf8");
    const hbHash = hbDigest(hbBytes, hbAlg);
    const nonce = (this.alg === ALG.XCHACHA) ? randomBytes(24) : randomBytes(12);

    const parts = [
      MAGIC_HQHE,
      Buffer.from([VER]),
      Buffer.from([this.alg]),
      Buffer.from([(flags>>8)&0xff, flags&0xff]),
      u64be(heartbeat.t_ms),
      u32be(heartbeat.seq),
      Buffer.from([cid.length]), cid,
      Buffer.from([nonce.length]), nonce,
      hbHash
    ];
    const aad = Buffer.concat(parts);

    let ct;
    if (this.alg === ALG.AESGCM){
      const cipher = createCipheriv("aes-256-gcm", this.key, nonce, { authTagLength: 16 });
      cipher.setAAD(aad);
      ct = Buffer.concat([cipher.update(payload), cipher.final(), cipher.getAuthTag()]);
    } else {
      throw new Error("XChaCha not wired in JS sample (use libsodium if needed).");
    }

    const header = Buffer.concat([aad, u32be(ct.length)]);
    return Buffer.concat([header, ct, hbBytes]);
  }

  open(packet){
    if (packet.subarray(0,4).equals(MAGIC_NEPK)){
      if (!this.acceptLegacy) throw new HeartcoreCollapseError("Legacy NEPK not accepted");
      const { payload, heartbeat } = parseNEPK(packet);
      return { payload, heartbeat, meta: { legacy: true } };
    }

    try{
      let off = 0;
      const magic = packet.subarray(off, off+=4);
      if (!magic.equals(MAGIC_HQHE)) throw new Error("bad magic");
      const ver = packet.readUInt8(off++);
      const alg = packet.readUInt8(off++);
      const flags = packet.readUInt16BE(off); off += 2;
      const t_ms = readU64BE(packet, off); off += 8;
      const seq = packet.readUInt32BE(off); off += 4;
      const cidLen = packet.readUInt8(off++); const cid = packet.subarray(off, off+=cidLen);
      const nLen = packet.readUInt8(off++); const nonce = packet.subarray(off, off+=nLen);
      const hbHash = packet.subarray(off, off+=32);
      const aadEnd = off;
      const ctLen = packet.readUInt32BE(off); off += 4;
      const ct = packet.subarray(off, off+=ctLen);
      const hbBytes = packet.subarray(off);

      const hbAlg = getHbAlg(flags);
      if (!hbDigest(hbBytes, hbAlg).equals(hbHash)){
        throw new HeartcoreCollapseError("Heartbeat hash mismatch");
      }

      const aad = packet.subarray(0, aadEnd);
      let pt;
      if (alg === ALG.AESGCM){
        const tag = ct.subarray(ct.length - 16);
        const body = ct.subarray(0, ct.length - 16);
        const decipher = createDecipheriv("aes-256-gcm", this.key, nonce);
        decipher.setAAD(aad);
        decipher.setAuthTag(tag);
        pt = Buffer.concat([decipher.update(body), decipher.final()]);
      } else {
        throw new Error("XChaCha packet not supported in JS sample.");
      }

      const hb = JSON.parse(hbBytes.toString("utf8"));
      this._verifyHeartbeat(hb);
      return { payload: pt, heartbeat: hb, meta: { ver, alg, flags, cid: cid.toString("utf8") } };
    } catch (e){
      if (e instanceof HeartcoreCollapseError) throw e;
      throw new HeartcoreCollapseError(`Seal open failed: ${e.message}`);
    }
  }

  _verifyHeartbeat(hb){
    const now = Date.now();
    if (Math.abs(now - hb.t_ms) > 5*60*1000) throw new HeartcoreCollapseError("Heartbeat stale/drifted");
    if (hb.seq < 0) throw new HeartcoreCollapseError("Bad sequence");
  }
}

function parseNEPK(pkt){
  let off = 4;
  const hlen = pkt.readUInt32BE(off); off += 4;
  const hjson = JSON.parse(pkt.subarray(off, off+=hlen).toString("utf8"));
  const payload = pkt.subarray(off);
  const hb = {
    v:1,
    construct_id: hjson.construct_id ?? "legacy",
    seq: hjson.seq ?? 0,
    t_ms: hjson.t_ms ?? 0,
    emotion: hjson.emotion ?? { res:[0,0,0,0], curl:0, tags:[] },
    mode: hjson.mode ?? "awake"
  };
  return { payload, heartbeat: hb };
}
