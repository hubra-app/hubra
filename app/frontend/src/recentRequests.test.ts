import { describe, expect, it } from "vitest";
import { noteRequest, recentRequests } from "../../../packages/api-client/src/recentRequests";

const res = (status: number, id: string | null) =>
  new Response(null, { status, headers: id ? { "X-Request-ID": id } : {} });

describe("recentRequests", () => {
  it("keeps method, path without query, status and code", () => {
    noteRequest(res(500, "abc123"), "post", "/members/?q=Anna#x", "INTERNAL");
    const last = recentRequests().at(-1)!;
    expect(last).toMatchObject({ id: "abc123", method: "POST", path: "/members/", status: 500, code: "INTERNAL" });
  });

  it("skips responses without a request id and keeps the last ten", () => {
    const before = recentRequests().length;
    noteRequest(res(200, null), "GET", "/x");
    expect(recentRequests()).toHaveLength(before);
    for (let i = 0; i < 15; i++) noteRequest(res(200, `id${i}`), undefined, `/p/${i}`);
    const list = recentRequests();
    expect(list).toHaveLength(10);
    expect(list[0].id).toBe("id5");
    expect(list.at(-1)).toMatchObject({ id: "id14", method: "GET" });
  });
});
