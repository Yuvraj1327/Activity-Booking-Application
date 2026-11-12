import { describe, expect, it } from "vitest";
import { duration, formatBucket, formatDate, formatMoney, titleCase, toneOf } from "@/lib/format";
import { href, one, pageOf, resolveRange, todayIn } from "@/lib/query";

describe("money formatting", () => {
  it("shows paise as rupees without rounding errors", () => {
    expect(formatMoney(75000)).toBe("₹750.00");
    expect(formatMoney(1)).toBe("₹0.01");
    expect(formatMoney(123456789)).toContain("12,34,567.89");
  });
  it("shows a dash for missing values and never invents zero", () => {
    expect(formatMoney(null)).toBe("—");
    expect(formatMoney(undefined)).toBe("—");
  });
  it("labels non-INR currencies plainly", () => {
    expect(formatMoney(5000, "USD")).toBe("50.00 USD");
  });
});

describe("labels", () => {
  it("titleCase and durations", () => {
    expect(titleCase("pending_payment")).toBe("Pending payment");
    expect(duration(45)).toBe("45 min");
    expect(duration(60)).toBe("1 h");
    expect(duration(90)).toBe("1 h 30 min");
  });
  it("status tones", () => {
    expect(toneOf("confirmed")).toBe("success");
    expect(toneOf("failed")).toBe("danger");
    expect(toneOf("pending_payment")).toBe("warning");
    expect(toneOf("something_new")).toBe("neutral");
  });
  it("plain dates are not shifted by time zone", () => {
    expect(formatDate("2026-03-01")).toBe("1 Mar 2026");
    expect(formatBucket("2026-03-01", "month")).toBe("Mar 26");
  });
});

describe("date ranges", () => {
  // 2026-11-12 02:00 UTC is already 07:30 on 12 Nov in India
  const now = new Date("2026-11-12T02:00:00Z");
  it("uses the reporting time zone for 'today'", () => {
    expect(todayIn("Asia/Kolkata", now)).toBe("2026-11-12");
    expect(todayIn("America/Los_Angeles", now)).toBe("2026-11-11");
  });
  it("presets", () => {
    expect(resolveRange({ range: "today" }, now)).toEqual({ from: "2026-11-12", to: "2026-11-12", preset: "today" });
    expect(resolveRange({ range: "7d" }, now)).toEqual({ from: "2026-11-06", to: "2026-11-12", preset: "7d" });
    expect(resolveRange({ range: "month" }, now)).toEqual({ from: "2026-11-01", to: "2026-11-12", preset: "month" });
    expect(resolveRange({}, now)).toEqual({ from: "2026-10-14", to: "2026-11-12", preset: "30d" });
  });
  it("custom range wins, and bad input falls back to the default", () => {
    expect(resolveRange({ from: "2026-01-01", to: "2026-01-31" }, now).preset).toBe("custom");
    expect(resolveRange({ from: "2026-02-01", to: "2026-01-31" }, now).preset).toBe("30d");
    expect(resolveRange({ from: "nope", to: "2026-01-31" }, now).preset).toBe("30d");
  });
  it("month boundaries", () => {
    expect(resolveRange({ range: "7d" }, new Date("2026-03-03T10:00:00Z")).from).toBe("2026-02-25");
  });
});

describe("url state", () => {
  it("builds links, dropping empty values", () => {
    expect(href("/owners", { q: "a b", page: "3" }, { page: undefined })).toBe("/owners?q=a+b");
    expect(href("/owners", {}, {})).toBe("/owners");
    expect(href("/owners", { status: "active" }, { page: "2" })).toBe("/owners?status=active&page=2");
  });
  it("reads first value and trims", () => {
    expect(one({ q: "  x " }, "q")).toBe("x");
    expect(one({ q: ["a", "b"] }, "q")).toBe("a");
    expect(one({ q: " " }, "q")).toBeUndefined();
  });
  it("page numbers are bounded", () => {
    expect(pageOf({ page: "3" })).toEqual({ offset: 40, page: 3 });
    for (const bad of ["0", "-1", "abc", "1.5", "999999"]) expect(pageOf({ page: bad }).page).toBe(1);
  });
});
