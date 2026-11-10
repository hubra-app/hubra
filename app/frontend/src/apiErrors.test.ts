import { afterEach, describe, expect, it } from "vitest";
import { localizeError } from "../../../packages/api-client/src/errors";

describe("localizeError", () => {
  afterEach(() => {
    document.documentElement.lang = "";
  });

  it("uses the fields the API sends, in German", () => {
    document.documentElement.lang = "de-CH";
    const text = localizeError(400, "VALIDATION_ERROR", "{'email': ['x']}", {
      email: ["Not a valid email address."],
    });
    expect(text).toMatch(/^Bitte prüfe die Eingaben:/);
  });

  it("lists the fields in English", () => {
    document.documentElement.lang = "en";
    const text = localizeError(400, "VALIDATION_ERROR", "ignored", { first_name: ["Missing data."] });
    expect(text).toBe("Please check: first name (Missing data.)");
  });

  it("prefers a specific code over the English wording", () => {
    document.documentElement.lang = "de";
    expect(localizeError(409, "LAST_OWNER", "Reworded message the map doesn't know")).toMatch(
      /letzte Inhaberin/,
    );
  });

  it("still parses the old message text when no fields come", () => {
    document.documentElement.lang = "en";
    expect(localizeError(400, "VALIDATION_ERROR", "{'name': ['Missing data.']}")).toBe(
      "Please check: name (Missing data.)",
    );
  });

  it("translates messages that carry a name", () => {
    document.documentElement.lang = "de";
    expect(localizeError(403, "LICENSE_REQUIRED", "You need a licence for Inventory; ask the club's admin")).toBe(
      "Für Inventory brauchst du eine Lizenz. Frag die Admins des Vereins.",
    );
    expect(localizeError(409, "MODULE_DEPENDENCY_OFF", "Switch on Finances first; Budgets needs it")).toBe(
      "Schalte zuerst Finances ein; Budgets braucht es.",
    );
  });

  it("calls a suspended membership gesperrt, like its status", () => {
    document.documentElement.lang = "de";
    expect(localizeError(403, "MEMBERSHIP_SUSPENDED", "Your membership in this club is suspended")).toMatch(
      /ist gesperrt/,
    );
  });
});
