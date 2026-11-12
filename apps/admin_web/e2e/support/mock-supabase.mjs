// Test-only stand-in for Supabase Auth, used by the Playwright suite.
// It signs HS256 tokens that the REAL FastAPI backend verifies with the shared test secret, so the
// admin web -> API -> Postgres path is genuine. It is never used outside e2e.
import { createHmac, randomUUID } from "node:crypto";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";

const PORT = Number(process.env.MOCK_SUPABASE_PORT ?? 54500);
const SECRET = process.env.E2E_JWT_SECRET ?? "e2e-secret-" + "x".repeat(40);
const ISSUER = process.env.E2E_JWT_ISSUER ?? "https://e2e.supabase.co/auth/v1";
const USERS_FILE = process.env.E2E_USERS_FILE;
const PASSWORDS = { "admin@zuruv.test": "E2E-admin-pass" };
const DEFAULT_PASSWORD = "E2E-user-pass";

const b64 = (o) => Buffer.from(typeof o === "string" ? o : JSON.stringify(o)).toString("base64url");
const sign = (claims) => {
  const head = b64({ alg: "HS256", typ: "JWT" });
  const body = b64(claims);
  const sig = createHmac("sha256", SECRET).update(`${head}.${body}`).digest("base64url");
  return `${head}.${body}.${sig}`;
};
function verify(token) {
  const [h, p, s] = (token ?? "").split(".");
  if (!h || !p || !s) return null;
  const expect = createHmac("sha256", SECRET).update(`${h}.${p}`).digest("base64url");
  if (expect !== s) return null;
  const claims = JSON.parse(Buffer.from(p, "base64url").toString());
  return claims.exp > Date.now() / 1000 ? claims : null;
}
const users = () => JSON.parse(readFileSync(USERS_FILE, "utf8"));

function session(email, id) {
  const now = Math.floor(Date.now() / 1000);
  const claims = {
    sub: id, aud: "authenticated", iss: ISSUER, iat: now, exp: now + 3600, role: "authenticated",
    email, phone: "", aal: "aal2", amr: [{ method: "password", timestamp: now }], session_id: randomUUID(),
    app_metadata: { provider: "email" }, user_metadata: {},
  };
  return {
    access_token: sign(claims), token_type: "bearer", expires_in: 3600, expires_at: now + 3600,
    refresh_token: "refresh." + b64({ email, id }),
    user: { id, aud: "authenticated", role: "authenticated", email, app_metadata: { provider: "email" }, user_metadata: {}, created_at: new Date().toISOString(), factors: [] },
  };
}

const json = (res, status, body) => {
  res.writeHead(status, { "content-type": "application/json", "access-control-allow-origin": "*", "access-control-allow-headers": "*" });
  res.end(JSON.stringify(body));
};

createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  if (req.method === "OPTIONS") return json(res, 204, {});
  let body = "";
  for await (const c of req) body += c;
  const data = body ? JSON.parse(body) : {};

  if (url.pathname === "/health") return json(res, 200, { ok: true });
  if (url.pathname === "/auth/v1/token" && req.method === "POST") {
    const grant = url.searchParams.get("grant_type");
    if (grant === "password") {
      const u = users()[String(data.email ?? "").toLowerCase()];
      const ok = u && data.password === (PASSWORDS[data.email] ?? DEFAULT_PASSWORD);
      return ok ? json(res, 200, session(data.email.toLowerCase(), u.id)) : json(res, 400, { code: 400, error_code: "invalid_credentials", msg: "Invalid login credentials" });
    }
    if (grant === "refresh_token") {
      try {
        const info = JSON.parse(Buffer.from(String(data.refresh_token).split(".")[1], "base64url").toString());
        return json(res, 200, session(info.email, info.id));
      } catch {
        return json(res, 400, { code: 400, error_code: "bad_refresh", msg: "bad refresh token" });
      }
    }
  }
  if (url.pathname === "/auth/v1/user" && req.method === "GET") {
    const claims = verify((req.headers.authorization ?? "").replace(/^Bearer /i, ""));
    if (!claims) return json(res, 401, { code: 401, error_code: "bad_jwt", msg: "invalid JWT" });
    return json(res, 200, { id: claims.sub, aud: "authenticated", role: "authenticated", email: claims.email, app_metadata: {}, user_metadata: {}, factors: [], created_at: new Date().toISOString() });
  }
  if (url.pathname === "/auth/v1/logout") return json(res, 204, {});
  return json(res, 404, { msg: "not mocked", path: url.pathname });
}).listen(PORT, "127.0.0.1", () => console.log(`mock supabase auth on ${PORT}`));
