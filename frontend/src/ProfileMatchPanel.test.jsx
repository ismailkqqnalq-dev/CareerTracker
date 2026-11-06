import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProfileMatchPanel from "./ProfileMatchPanel.jsx";

afterEach(cleanup);

function createApi() {
  const profileSkills = [
    { id: 4, skill_id: 1, proficiency_level: "intermediate", years_experience: 2 },
  ];
  const skills = [
    { id: 1, name: "Python", category: "language" },
    { id: 2, name: "PostgreSQL", category: "database" },
  ];
  const opportunities = [
    { id: 17, company: "Örnek AŞ", position: "Backend Developer" },
  ];
  const requiredSkills = [skills[0]];
  const requestAll = vi.fn(async (path) => {
    if (path === "/users/me/skills") return [...profileSkills];
    if (path === "/opportunities") return opportunities;
    throw new Error(`Unexpected list request: ${path}`);
  });
  const request = vi.fn(async (path, options = {}) => {
    if (path === "/users/me/skills" && options.method === "POST") {
      const body = JSON.parse(options.body);
      const created = { id: 5, ...body };
      profileSkills.push(created);
      return created;
    }
    if (path === "/users/me/skills/4" && options.method === "PATCH") {
      return { id: 4, skill_id: 1, ...JSON.parse(options.body) };
    }
    if (path === "/users/me/skills/4" && options.method === "DELETE") return null;
    if (path === "/opportunities/17/skills" && options.method === "POST") {
      const created = skills.find((item) => item.name === JSON.parse(options.body).skill);
      requiredSkills.push(created);
      return created;
    }
    if (path === "/opportunities/17/skills") return [...requiredSkills];
    if (path === "/opportunities/17/skill-match") {
      return {
        opportunity_id: 17,
        required_skill_count: 2,
        matched_skill_count: 1,
        match_percentage: 50,
        matched_skills: [skills[0]],
        missing_skills: [skills[1]],
      };
    }
    throw new Error(`Unexpected request: ${path}`);
  });
  return { request, requestAll };
}

const props = (api) => ({ api, token: "test-token", skills: [
  { id: 1, name: "Python", category: "language" },
  { id: 2, name: "PostgreSQL", category: "database" },
] });

describe("profile skills and opportunity matching", () => {
  it("loads the user's profile and opportunities and lets them add a skill", async () => {
    const api = createApi();
    render(<ProfileMatchPanel {...props(api)} />);

    expect(await screen.findByText("Python")).toBeTruthy();
    expect(screen.getByRole("option", { name: /Örnek AŞ/ })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Yeni profil becerisi"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Profile ekle" }));

    expect(api.request).toHaveBeenCalledWith("/users/me/skills", expect.objectContaining({
      method: "POST",
      token: "test-token",
      body: JSON.stringify({ skill_id: 2, proficiency_level: "beginner", years_experience: 0 }),
    }));
    expect(await screen.findByText("PostgreSQL")).toBeTruthy();
  });

  it("updates and removes only the selected user's profile skill", async () => {
    const api = createApi();
    render(<ProfileMatchPanel {...props(api)} />);

    await screen.findByText("Python");
    fireEvent.change(screen.getByLabelText("Python yetkinlik seviyesi"), { target: { value: "advanced" } });
    fireEvent.change(screen.getByLabelText("Python yıl deneyimi"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Python kaydet" }));

    expect(api.request).toHaveBeenCalledWith("/users/me/skills/4", expect.objectContaining({
      method: "PATCH",
      body: JSON.stringify({ proficiency_level: "advanced", years_experience: 4 }),
    }));
    expect(await screen.findByRole("status")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Python profilinden kaldır" }));
    expect(api.request).toHaveBeenCalledWith("/users/me/skills/4", expect.objectContaining({ method: "DELETE" }));
  });

  it("shows matched and missing skills for a selected opportunity", async () => {
    const api = createApi();
    render(<ProfileMatchPanel {...props(api)} />);

    await screen.findByText("Python");
    fireEvent.change(screen.getByLabelText("Fırsat seç"), { target: { value: "17" } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Eşleşmeyi hesapla" }).disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "Eşleşmeyi hesapla" }));

    expect(await screen.findByRole("heading", { name: "Eşleşme sonucu" })).toBeTruthy();
    expect(screen.getByText("%50 eşleşme")).toBeTruthy();
    expect(screen.getAllByText("Python", { selector: "strong" })).toHaveLength(2);
    expect(screen.getByText("PostgreSQL", { selector: "strong" })).toBeTruthy();
  });

  it("lets the user attach a catalog skill to an opportunity before matching", async () => {
    const api = createApi();
    render(<ProfileMatchPanel {...props(api)} />);

    await screen.findByLabelText("Python yetkinlik seviyesi");
    fireEvent.change(screen.getByLabelText("Fırsat seç"), { target: { value: "17" } });
    fireEvent.change(screen.getByLabelText("Fırsat becerisi ekle"), { target: { value: "2" } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Gerekli beceri ekle" }).disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "Gerekli beceri ekle" }));

    expect(api.request).toHaveBeenCalledWith("/opportunities/17/skills", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ skill: "PostgreSQL" }),
    }));
    expect(await screen.findByText("Beceri fırsatın gereksinimlerine eklendi.")).toBeTruthy();
  });
});
