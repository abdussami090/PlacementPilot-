import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/App.jsx";

const { apiRequestMock, apiBlobRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
  apiBlobRequestMock: vi.fn(),
}));

vi.mock("../src/api.js", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    apiRequest: apiRequestMock,
    apiBlobRequest: apiBlobRequestMock,
  };
});

const student = { id: 8, name: "Test Student", email: "student@example.test", role: "student" };
const admin = { id: 1, name: "Placement Admin", email: "admin@example.test", role: "admin" };

function job(role = "Software Engineer") {
  return {
    id: 41,
    role,
    package: "Test fixture",
    location: "Remote",
    is_saved: false,
    company: { name: "Authorized Test Company" },
    recruitment_drive: {
      name: "Published test drive",
      application_deadline: "2099-12-01",
    },
    eligibility: { eligible: true, reasons: [] },
  };
}

function mockAuthenticatedUser(user = student) {
  apiRequestMock.mockImplementation(async (path) => {
    if (path === "/auth/login") return { access_token: "mock-token" };
    if (path === "/auth/signup") return { message: "Student account created successfully" };
    if (path === "/auth/me") return user;
    if (path === "/student/dashboard") {
      return {
        statistics: {
          total_applications: 2,
          active_applications: 1,
          offers_released: 0,
          saved_jobs: 1,
        },
        applications_by_status: { Applied: 2 },
        upcoming_rounds: [],
      };
    }
    if (path.startsWith("/student/jobs?")) {
      return {
        items: [job()],
        pagination: {
          page: 1,
          page_size: 9,
          total_items: 1,
          total_pages: 1,
          has_next: false,
          has_previous: false,
        },
      };
    }
    if (path === "/student/saved-jobs?page=1&page_size=50") {
      return { items: [], pagination: { page: 1, page_size: 50, total_items: 0 } };
    }
    if (path === "/profile") return { college: "Example College", branch: "Computing", year: "2026" };
    if (path === "/education" || path === "/skills" || path === "/resume") return [];
    if (path === "/resume/uploaded") return null;
    if (path === "/admin/dashboard/overview") return { total_students: 3, total_jobs: 2 };
    if (path === "/admin/users") return [{ ...student, id: 8 }];
    return { message: "ok" };
  });
}

async function signIn(email = student.email) {
  fireEvent.change(screen.getByLabelText("Email address"), { target: { value: email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "SafeTestPassword123!" } });
  fireEvent.click(screen.getByRole("button", { name: /sign in securely/i }));
}

describe("PlacementPilot application flows (API mocked)", () => {
  beforeEach(() => {
    sessionStorage.clear();
    apiRequestMock.mockReset();
    apiBlobRequestMock.mockReset();
    vi.stubGlobal("confirm", vi.fn(() => true));
    mockAuthenticatedUser();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("keeps portal navigation protected and logs an authenticated student out", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Sign in to your account" })).toBeTruthy();
    expect(screen.queryByRole("navigation")).toBeNull();
    await signIn();

    expect(await screen.findByText("Keep moving forward.")).toBeTruthy();
    expect(screen.getByText("2", { selector: ".stat-card strong" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /find jobs/i })).toBeTruthy();
    expect(sessionStorage.getItem("placementpilot_token")).toBe("mock-token");

    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(await screen.findByRole("heading", { name: "Sign in to your account" })).toBeTruthy();
    expect(sessionStorage.getItem("placementpilot_token")).toBeNull();
    expect(screen.queryByRole("button", { name: /find jobs/i })).toBeNull();
  });

  it("enforces signup password length and submits student registration", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Create an account" }));

    expect(screen.getByRole("heading", { name: "Create your student account" })).toBeTruthy();
    const password = screen.getByLabelText("Password");
    expect(password.minLength).toBe(12);
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "New Student" } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "new@example.test" } });
    fireEvent.change(password, { target: { value: "ValidTestPass123!" } });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith(
        "/auth/signup",
        expect.objectContaining({
          method: "POST",
          body: {
            name: "New Student",
            email: "new@example.test",
            password: "ValidTestPass123!",
          },
        }),
      );
    });
    expect(await screen.findByText("Keep moving forward.")).toBeTruthy();
  });

  it("loads and filters official jobs and submits an application", async () => {
    render(<App />);
    await signIn();
    await screen.findByText("Keep moving forward.");
    fireEvent.click(screen.getByRole("button", { name: /find jobs/i }));

    expect(await screen.findByRole("heading", { name: "Software Engineer" })).toBeTruthy();
    expect(screen.getByText("Authorized Test Company")).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("Search role, company or drive"), {
      target: { value: "Engineer" },
    });
    fireEvent.change(screen.getByPlaceholderText("Location"), { target: { value: "Remote" } });
    fireEvent.click(screen.getByRole("button", { name: "Search jobs" }));

    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith(
        "/student/jobs?page=1&page_size=9&search=Engineer&location=Remote",
        expect.objectContaining({ token: "mock-token" }),
      );
    });
    fireEvent.click(screen.getByRole("button", { name: /apply now/i }));
    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith(
        "/apply",
        expect.objectContaining({ method: "POST", body: { job_id: 41 } }),
      );
    });
    expect(await screen.findByText(/Application submitted successfully/)).toBeTruthy();
  });

  it("shows only administrator navigation and loads student management", async () => {
    mockAuthenticatedUser(admin);
    render(<App />);
    await signIn(admin.email);

    expect(await screen.findByText("Manage the placement lifecycle.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /students/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /find jobs/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /students/i }));

    expect(await screen.findByText("student@example.test")).toBeTruthy();
    const row = screen.getByText("student@example.test").closest("tr");
    expect(within(row).getByRole("button", { name: "Delete account" })).toBeTruthy();
  });

  it("lets placement administrators configure job eligibility", async () => {
    mockAuthenticatedUser(admin);
    apiRequestMock.mockImplementation(async (path, options = {}) => {
      if (path === "/auth/login") return { access_token: "mock-token" };
      if (path === "/auth/me") return admin;
      if (path === "/admin/dashboard/overview") return { users: { students: 1 } };
      if (path === "/admin/jobs") {
        return [{
          id: 41,
          role: "Software Engineer",
          company: "Authorized Test Company",
          recruitment_drive: "Published test drive",
          package: "Test fixture",
          location: "Remote",
          status: "Open",
        }];
      }
      if (path === "/admin/recruitment-drives") return [];
      if (path === "/admin/jobs/41/eligibility" && options.method === "POST") {
        return { job_id: 41, eligible_courses: ["B.Tech"] };
      }
      if (path === "/admin/jobs/41/eligibility") {
        const error = new Error("Eligibility criteria not found");
        error.status = 404;
        throw error;
      }
      return { message: "ok" };
    });

    render(<App />);
    await signIn(admin.email);
    await screen.findByText("Manage the placement lifecycle.");
    fireEvent.click(screen.getByRole("button", { name: /jobs/i }));
    expect(await screen.findByLabelText("Job position for eligibility")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Job position for eligibility"), {
      target: { value: "41" },
    });
    fireEvent.change(screen.getByLabelText("Eligible courses"), {
      target: { value: "B.Tech, B.Sc" },
    });
    fireEvent.change(screen.getByLabelText("Minimum CGPA"), {
      target: { value: "7.5" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save criteria/i }));

    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith(
        "/admin/jobs/41/eligibility",
        expect.objectContaining({
          method: "POST",
          body: expect.objectContaining({
            eligible_courses: ["B.Tech", "B.Sc"],
            min_cgpa: 7.5,
          }),
        }),
      );
    });
    expect(await screen.findByText(/Job eligibility created\./)).toBeTruthy();
  });

  it("surfaces resume upload errors instead of showing success", async () => {
    apiRequestMock.mockImplementation(async (path, options = {}) => {
      if (path === "/auth/login") return { access_token: "mock-token" };
      if (path === "/auth/me") return student;
      if (path === "/student/dashboard") return { statistics: {}, applications_by_status: {}, upcoming_rounds: [] };
      if (path === "/profile") return { college: "Example College" };
      if (path === "/education" || path === "/skills" || path === "/resume") return [];
      if (path === "/resume/uploaded") return null;
      if (path === "/resume/upload" && options.method === "POST") throw new Error("Resume storage is unavailable");
      return { message: "ok" };
    });
    render(<App />);
    await signIn();
    await screen.findByText("Keep moving forward.");
    fireEvent.click(screen.getByRole("button", { name: /my profile/i }));
    await screen.findByText("Personal and academic profile");
    fireEvent.click(screen.getByRole("tab", { name: /resume/i }));

    const file = new File(["%PDF-1.7\nmock\n%%EOF\n"], "resume.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Resume PDF"), { target: { files: [file] } });
    fireEvent.submit(screen.getByLabelText("Resume PDF").closest("form"));

    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith(
        "/resume/upload",
        expect.objectContaining({ method: "POST" }),
      );
    });
    expect(await screen.findByText("Resume storage is unavailable")).toBeTruthy();
    expect(screen.queryByText("PDF resume uploaded successfully.")).toBeNull();
  });

  it("returns an expired stored token to the sign-in screen", async () => {
    sessionStorage.setItem("placementpilot_token", "expired-token");
    apiRequestMock.mockRejectedValueOnce(new Error("expired"));
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Sign in to your account" })).toBeTruthy();
    expect(sessionStorage.getItem("placementpilot_token")).toBeNull();
  });
});
