import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState, ErrorState, UnavailableNote } from "@/components/data/states";
import { FilterBar } from "@/components/data/filter-bar";
import { Pagination } from "@/components/data/pagination";
import { StatCard } from "@/components/data/stat-card";
import { StatusBadge } from "@/components/data/status-badge";
import { MoneyPanel } from "@/components/data/money-panel";
import { DateRangeFilter } from "@/components/data/date-range-filter";
import { DonutChart, TrendChart } from "@/components/charts/charts-impl";
import Loading from "@/app/(dashboard)/loading";
import type { Money } from "@/lib/types";

const money: Money = {
  currency: "INR",
  gross_booking_value_paise: 250000,
  successful_payment_paise: 200000,
  platform_revenue: { available: false, depends_on: "Q7, Q8", message: "x" },
  owner_earnings: { available: false, depends_on: "Q10", message: "x" },
  refunds: { available: false, depends_on: "Q9", message: "x" },
};

describe("states", () => {
  it("loading skeleton is announced", () => {
    render(<Loading />);
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
  });
  it("empty and error states", () => {
    render(<><EmptyState title="Nothing here" description="Try again" /><ErrorState message="Boom" /></>);
    expect(screen.getByTestId("empty-state")).toHaveTextContent("Nothing here");
    expect(screen.getByRole("alert")).toHaveTextContent("Boom");
  });
  it("unavailable data names the rule it waits for", () => {
    render(<UnavailableNote what="Refund records" depends="Q9" />);
    expect(screen.getByTestId("unavailable-note")).toHaveTextContent("not available");
  });
});

describe("tables and filters", () => {
  it("pagination: first page of many", () => {
    render(<Pagination path="/bookings" params={{ status: "confirmed" }} page={1} hasMore shown={20} />);
    expect(screen.getByRole("link", { name: /Next/ })).toHaveAttribute("href", "/bookings?status=confirmed&page=2");
    expect(screen.queryByRole("link", { name: /Previous/ })).toBeNull();
  });
  it("pagination: middle and last page keep filters", () => {
    const { rerender } = render(<Pagination path="/b" params={{ q: "x" }} page={3} hasMore shown={20} />);
    expect(screen.getByRole("link", { name: /Previous/ })).toHaveAttribute("href", "/b?q=x&page=2");
    rerender(<Pagination path="/b" params={{ q: "x" }} page={2} hasMore={false} shown={4} />);
    expect(screen.getByRole("link", { name: /Previous/ })).toHaveAttribute("href", "/b?q=x");
    expect(screen.queryByRole("link", { name: /Next/ })).toBeNull();
  });
  it("pagination hidden when everything fits on one page", () => {
    const { container } = render(<Pagination path="/b" params={{}} page={1} hasMore={false} shown={3} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("filter bar keeps current values and offers Clear only when filtering", () => {
    const fields = [
      { kind: "search" as const, name: "q", placeholder: "Search" },
      { kind: "select" as const, name: "status", label: "Status", options: ["active", "suspended"] },
    ];
    const first = render(<FilterBar path="/owners" params={{}} fields={fields} />);
    expect(screen.queryByRole("link", { name: "Clear" })).toBeNull();
    first.unmount(); // a filter change is a new page load, so the form is rebuilt, not re-rendered
    render(<FilterBar path="/owners" params={{ q: "abc", status: "suspended" }} fields={fields} />);
    expect(screen.getByPlaceholderText("Search")).toHaveValue("abc");
    expect(screen.getByLabelText("Status")).toHaveValue("suspended");
    expect(screen.getByRole("link", { name: "Clear" })).toHaveAttribute("href", "/owners");
    expect(screen.getByRole("search")).toHaveAttribute("method", "get");
  });
  it("status badges", () => {
    render(<StatusBadge status="pending_payment" />);
    expect(screen.getByText("Pending payment")).toBeInTheDocument();
  });
});

describe("dashboard pieces", () => {
  it("stat card", () => {
    render(<StatCard label="Customers" value="42" hint="3 new" />);
    expect(screen.getByTestId("stat-value")).toHaveTextContent("42");
  });
  it("money panel never shows a number for unapproved figures", () => {
    render(<MoneyPanel money={money} />);
    const panel = within(screen.getByTestId("money-panel"));
    expect(panel.getByTestId("money-gross")).toHaveTextContent("₹2,500.00");
    expect(panel.getByTestId("money-paid")).toHaveTextContent("₹2,000.00");
    for (const id of ["money-platform-revenue", "money-owner-earnings", "money-refunds"]) {
      expect(panel.getByTestId(id)).toHaveTextContent("Not available");
    }
    expect(panel.getByText(/Q7, Q8/)).toBeInTheDocument();
  });
  it("date presets mark the active one and keep other filters in the custom form", () => {
    render(<DateRangeFilter path="/analytics" params={{ tab: "revenue", range: "7d" }} range={{ from: "2026-11-06", to: "2026-11-12", preset: "7d" }} />);
    expect(screen.getByRole("link", { name: "Last 7 days" })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("link", { name: "Today" })).toHaveAttribute("href", "/analytics?tab=revenue&range=today");
    expect(document.querySelector('input[type=hidden][name=tab]')).toHaveAttribute("value", "revenue");
  });
});

describe("charts", () => {
  it("show an empty message when there is no data", () => {
    render(<TrendChart title="t" data={[{ label: "1 Nov", Bookings: 0 }]} series={[{ key: "Bookings", label: "Bookings" }]} />);
    expect(screen.getByTestId("chart-empty")).toHaveTextContent("No data in this period");
    render(<DonutChart title="d" data={[]} />);
    expect(screen.getAllByTestId("chart-empty")).toHaveLength(2);
  });
  it("render a labelled figure when data exists", () => {
    render(<TrendChart title="Booking trend" data={[{ label: "1 Nov", Bookings: 3 }]} series={[{ key: "Bookings", label: "Bookings" }]} />);
    expect(screen.getByRole("figure", { name: "Booking trend" })).toBeInTheDocument();
    expect(screen.queryByTestId("chart-empty")).toBeNull();
  });
});
