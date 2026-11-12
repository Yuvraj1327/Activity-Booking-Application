import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

export const AUTH = "http://127.0.0.1:54500";
export const API = "http://127.0.0.1:8018/api/v1";
export const ADMIN = { email: "admin@zuruv.test", password: "E2E-admin-pass" };
export const USER_PASSWORD = "E2E-user-pass";

export const users = (): Record<string, { id: string; role: string }> => JSON.parse(readFileSync("e2e/.stack/users.json", "utf8"));

export async function tokenFor(request: APIRequestContext, email: string, password: string): Promise<string> {
  const r = await request.post(`${AUTH}/auth/v1/token?grant_type=password`, { data: { email, password } });
  expect(r.ok()).toBeTruthy();
  return (await r.json()).access_token;
}

export const adminToken = (request: APIRequestContext) => tokenFor(request, ADMIN.email, ADMIN.password);

export async function api<T>(request: APIRequestContext, path: string, token: string): Promise<T> {
  const r = await request.get(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  expect(r.ok(), `${path} -> ${r.status()}`).toBeTruthy();
  return (await r.json()) as T;
}

export async function signIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Wait for the table (or empty state) of a list page. */
export async function rowsOf(page: Page) {
  await page.getByRole("table").first().waitFor();
  return page.locator("tbody tr");
}
