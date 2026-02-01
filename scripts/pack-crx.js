#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const os = require("os");
const crypto = require("crypto");
const { execFileSync } = require("child_process");

function usage() {
  console.error("Usage: node pack-crx.js <extension-dir> <key.pem> <output.crx>");
  process.exit(1);
}

const [extDir, keyPath, outPath] = process.argv.slice(2);
if (!extDir || !keyPath || !outPath) usage();

const absExtDir = path.resolve(extDir);
const absKey = path.resolve(keyPath);
const absOut = path.resolve(outPath);

if (!fs.existsSync(absExtDir)) {
  console.error(`Extension dir not found: ${absExtDir}`);
  process.exit(1);
}
if (!fs.existsSync(absKey)) {
  console.error(`Key not found: ${absKey}`);
  process.exit(1);
}

const tmpZip = path.join(os.tmpdir(), `ext-${Date.now()}.zip`);
try {
  execFileSync("zip", ["-qr", tmpZip, "."], { cwd: absExtDir });
} catch (err) {
  console.error("Failed to zip extension. Ensure 'zip' is installed.");
  throw err;
}

const zipData = fs.readFileSync(tmpZip);
const keyPem = fs.readFileSync(absKey);
const privateKey = crypto.createPrivateKey(keyPem);
const publicKeyDer = crypto.createPublicKey(privateKey).export({ type: "spki", format: "der" });
const signature = crypto.sign("RSA-SHA1", zipData, privateKey);

const header = Buffer.alloc(16);
header.write("Cr24", 0);
header.writeUInt32LE(2, 4);
header.writeUInt32LE(publicKeyDer.length, 8);
header.writeUInt32LE(signature.length, 12);

const crx = Buffer.concat([header, publicKeyDer, signature, zipData]);
fs.mkdirSync(path.dirname(absOut), { recursive: true });
fs.writeFileSync(absOut, crx);

fs.unlinkSync(tmpZip);
console.log(`Wrote ${absOut}`);
