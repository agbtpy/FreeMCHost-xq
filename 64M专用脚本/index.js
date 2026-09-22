#!/usr/bin/env node
process.chdir(__dirname);
const SHARED_PORT = 6666; // 改端口
const COMMON_UUID = "8de2090b-061b-40bc-aeb6-7ca234e067ee"; // 改UUID
const MASQ_DOMAIN = "www.apple.com"; // 可以默认
const { execSync, spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const SERVER_JSON = "config.json";
const CERT = "sbt-cert.pem";
const KEY = "sbt-key.pem";
const BIN = "./sb-box";
const SING_BOX_VERSION = "1.9.4";

const run = c => {
  try {
    return execSync(c, { encoding: 'utf-8', stdio: 'pipe' }).trim();
  } catch {
    return null;
  }
};

if (!fs.existsSync(CERT) || !fs.existsSync(KEY)) {
  run(`openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -keyout ${KEY} -out ${CERT} -subj "/CN=${MASQ_DOMAIN}" -days 3650 -nodes >/dev/null 2>&1`);
  if (fs.existsSync(KEY)) fs.chmodSync(KEY, 0o600);
}

if (!fs.existsSync(BIN)) {
  const archMap = { x64: 'amd64', arm64: 'arm64' };
  const a = archMap[os.arch()] || null;

  if (a) {
    run(`curl -sLfo sb.tar.gz https://github.com/SagerNet/sing-box/releases/download/v${SING_BOX_VERSION}/sing-box-${SING_BOX_VERSION}-linux-${a}.tar.gz`);
    run(`tar -xzf sb.tar.gz --strip-components=1 sing-box-${SING_BOX_VERSION}-linux-${a}/sing-box`);

    if (fs.existsSync('sing-box')) fs.renameSync('sing-box', BIN);
    if (fs.existsSync(BIN)) fs.chmodSync(BIN, 0o755);
    if (fs.existsSync('sb.tar.gz')) fs.unlinkSync('sb.tar.gz');
  }
} else {
  fs.chmodSync(BIN, 0o755);
}

if (!fs.existsSync(BIN)) {
  console.error('sing-box binary missing');
  process.exit(1);
}

fs.writeFileSync(SERVER_JSON, JSON.stringify({
  log: { disabled: true },
  inbounds: [
    {
      type: "tuic",
      tag: "tuic-in",
      listen: "::",
      listen_port: SHARED_PORT,
      users: [{ uuid: "78f7be17-bcc2-46a1-b39c-f49ca01044d1", password: COMMON_UUID }],
      congestion_control: "bbr",
      auth_timeout: "3s",
      zero_rtt_handshake: false,
      heartbeat: "10s",
      tls: {
        enabled: true,
        alpn: ["h3"],
        cipher_suites: ["TLS_AES_128_GCM_SHA256"],
        certificate_path: CERT,
        key_path: KEY
      }
    },
    {
      type: "vless",
      tag: "vless-ws-in",
      listen: "::",
      listen_port: SHARED_PORT,
      users: [{ uuid: COMMON_UUID }],
      transport: {
        type: "ws",
        path: "/ws",
        headers: { Host: MASQ_DOMAIN },
        max_early_data: 4096,
        early_data_header_name: "Sec-WebSocket-Protocol"
      }
    }
  ],
  outbounds: [{ type: "direct", tag: "direct" }]
}));
const ip = "127.0.0.1"; // ip可以输出节点手动改
console.log(`tuic://78f7be17-bcc2-46a1-b39c-f49ca01044d1:${COMMON_UUID}@${ip}:${SHARED_PORT}?congestion_control=bbr&alpn=h3&allowInsecure=1&sni=${MASQ_DOMAIN}&udp_relay_mode=native&disable_sni=0&reduce_rtt=1&max_udp_relay_packet_size=8192#TUIC
vless://${COMMON_UUID}@${ip}:${SHARED_PORT}?encryption=none&security=none&type=ws&host=${MASQ_DOMAIN}&path=%2Fws%3Fed%3D4096#VLESS`);

if (fs.existsSync('start.sh')) {
  fs.chmodSync('start.sh', 0o755);
}

if (process.argv.includes('--prepare')) {
  process.exit(0);
}

const p = spawn('sh', ['start.sh'], {
  stdio: ['ignore', 'ignore', 'ignore']
});

p.on('exit', (code, signal) => {
  process.exit(code ?? (signal ? 1 : 0));
});

p.on('error', () => {
  process.exit(1);
});
