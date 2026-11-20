import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppearanceSection } from "@/components/settings/appearance-section";
import { NotificationsSection } from "@/components/settings/notifications-section";
import { ProfileSection } from "@/components/settings/profile-section";
import { ThemeProvider } from "@/lib/theme";
import type { MyProfile } from "@/lib/types";

const actions = vi.hoisted(() => ({
  updateProfile: vi.fn(),
  saveAvatarPath: vi.fn(),
  savePreferences: vi.fn(),
}));
vi.mock("@/app/(dashboard)/settings/actions", () => actions);
vi.mock("@/lib/supabase/client", () => ({ getSupabaseClient: () => null }));

const profile: MyProfile = {
  id: "11111111-1111-1111-1111-111111111111",
  role: "admin",
  status: "active",
  full_name: "Asha Admin",
  email: "asha@example.com",
  phone: null,
  avatar_path: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  document.documentElement.classList.remove("dark");
  window.matchMedia = ((q: string) => ({
    matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
});

describe("appearance", () => {
  it("applies and persists the chosen theme", async () => {
    render(<ThemeProvider><AppearanceSection /></ThemeProvider>);
    await userEvent.click(screen.getByRole("radio", { name: /dark/i }));
    await waitFor(() => expect(document.documentElement).toHaveClass("dark"));
    expect(localStorage.getItem("zuruv-admin-theme")).toBe("dark");
    await userEvent.click(screen.getByRole("radio", { name: /light/i }));
    await waitFor(() => expect(document.documentElement).not.toHaveClass("dark"));
    expect(localStorage.getItem("zuruv-admin-theme")).toBe("light");
  });

  it("defaults to Light when nothing is saved, even if the OS prefers dark", async () => {
    window.matchMedia = ((q: string) => ({
      matches: true, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia;
    render(<ThemeProvider><AppearanceSection /></ThemeProvider>);
    await waitFor(() => expect(screen.getByRole("radio", { name: /light/i })).toHaveAttribute("aria-checked", "true"));
    expect(document.documentElement).not.toHaveClass("dark");
  });

  it("restores a saved theme on load", async () => {
    localStorage.setItem("zuruv-admin-theme", "dark");
    render(<ThemeProvider><AppearanceSection /></ThemeProvider>);
    await waitFor(() => expect(screen.getByRole("radio", { name: /dark/i })).toHaveAttribute("aria-checked", "true"));
    expect(document.documentElement).toHaveClass("dark");
  });
});

describe("notifications", () => {
  it("saves a toggle through the API action and shows the result", async () => {
    actions.savePreferences.mockResolvedValue({ ok: true, message: "Notification preferences saved.", data: { push_enabled: true, email_enabled: false } });
    render(<NotificationsSection initial={{ push_enabled: true, email_enabled: true }} />);
    await userEvent.click(screen.getByRole("switch", { name: /email notifications/i }));
    expect(actions.savePreferences).toHaveBeenCalledWith({ email_enabled: false });
    expect(await screen.findByText("Notification preferences saved.")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: /email notifications/i })).toHaveAttribute("aria-checked", "false");
  });

  it("rolls the toggle back when saving fails", async () => {
    actions.savePreferences.mockResolvedValue({ ok: false, message: "The ZURUV API is unreachable." });
    render(<NotificationsSection initial={{ push_enabled: true, email_enabled: true }} />);
    await userEvent.click(screen.getByRole("switch", { name: /push notifications/i }));
    expect(await screen.findByText("The ZURUV API is unreachable.")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: /push notifications/i })).toHaveAttribute("aria-checked", "true");
  });
});

describe("profile", () => {
  it("validates before calling the API", async () => {
    render(<ProfileSection profile={profile} email={profile.email} avatarUrl={null} />);
    const name = screen.getByLabelText("Full name");
    await userEvent.clear(name);
    await userEvent.type(name, "  ");
    fireEvent.submit(name.closest("form")!);
    expect(await screen.findByText("Enter your name.")).toBeInTheDocument();
    await userEvent.clear(name);
    await userEvent.type(name, "Asha");
    await userEvent.type(screen.getByLabelText(/phone/i), "12345");
    fireEvent.submit(name.closest("form")!);
    expect(await screen.findByText(/international format/i)).toBeInTheDocument();
    expect(actions.updateProfile).not.toHaveBeenCalled();
  });

  it("saves name and phone and shows success", async () => {
    actions.updateProfile.mockResolvedValue({ ok: true, message: "Profile saved.", data: { ...profile, full_name: "Asha Rao", phone: "+919876543210" } });
    render(<ProfileSection profile={profile} email={profile.email} avatarUrl={null} />);
    const name = screen.getByLabelText("Full name");
    await userEvent.clear(name);
    await userEvent.type(name, "Asha Rao");
    await userEvent.type(screen.getByLabelText(/phone/i), "+919876543210");
    await act(async () => fireEvent.submit(name.closest("form")!));
    expect(actions.updateProfile).toHaveBeenCalledWith({ full_name: "Asha Rao", phone: "+919876543210" });
    expect(await screen.findByText("Profile saved.")).toBeInTheDocument();
  });

  it("shows the email read-only and rejects a non-image photo", async () => {
    render(<ProfileSection profile={profile} email={profile.email} avatarUrl={null} />);
    expect(screen.getByLabelText("Email")).toBeDisabled();
    const input = screen.getByTestId("avatar-input") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "a.gif", { type: "image/gif" })] } });
    expect(await screen.findByText("Choose a JPG, PNG or WebP image.")).toBeInTheDocument();
  });
});

describe("sign out", () => {
  it("needs a second click to confirm and does nothing on the first", async () => {
    const signOut = vi.fn().mockResolvedValue({});
    vi.doMock("@/lib/supabase/client", () => ({ getSupabaseClient: () => ({ auth: { signOut } }) }));
    vi.doMock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }) }));
    vi.resetModules();
    const { SignOutButton } = await import("@/components/layout/sign-out-button");
    render(<SignOutButton />);
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(signOut).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirm sign out?" }));
    await waitFor(() => expect(signOut).toHaveBeenCalledTimes(1));
  });
});
