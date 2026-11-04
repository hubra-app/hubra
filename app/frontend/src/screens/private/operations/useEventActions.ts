import i18n from "i18next";
import { useMutation } from "@tanstack/react-query";
import { useToast, useAuth } from "@/context/AppContext";
import { qk } from "@/data/keys";
import { useListCache, useMyJoinedEvents } from "@/data/lists";
import { joinEvent, leaveEvent, maybeEvent } from "@/api/events";
import type { ClubEvent } from "@/types";

// A sign-up the member still has: the button then withdraws it.
const OPEN_STATUSES = new Set(["registered", "approved", "waitlisted", "pending", "attended"]);
// Those that hold a place (the member is on the attendee list).
const PLACE_STATUSES = new Set(["registered", "approved", "attended"]);

export function hasOpenSignUp(ev: ClubEvent, joined: boolean): boolean {
  return joined || OPEN_STATUSES.has(ev.myStatus ?? "");
}

export function useToggleJoinEvent() {
  const { notify } = useToast();
  const { currentUser } = useAuth();
  const myJoinedEvents = useMyJoinedEvents();
  const events = useListCache<ClubEvent>(qk.events);

  return useMutation({
    mutationFn: async ({
      eventId,
      eventTitle,
      memberId,
    }: {
      eventId: string;
      eventTitle: string;
      memberId: string;
    }) => {
      const ev = events.get()?.find((e) => e.id === eventId);
      const isJoined = ev
        ? hasOpenSignUp(ev, myJoinedEvents.has(eventId))
        : myJoinedEvents.has(eventId);
      let status: string | null = null;
      if (isJoined) {
        await leaveEvent(eventId, memberId);
      } else {
        status = await joinEvent(eventId, memberId);
      }
      return { isJoined, eventTitle, eventId, status };
    },
    onSuccess: ({ isJoined, eventTitle, eventId, status }) => {
      const me = currentUser?.id ?? "";
      events.patch(eventId, (ev) => {
        const holds = !isJoined && PLACE_STATUSES.has(status ?? "");
        const attendees = ev.attendees.filter((id) => id !== me);
        return {
          ...ev,
          myStatus: isJoined ? null : (status as ClubEvent["myStatus"]),
          attendees: holds ? [...attendees, me] : attendees,
        };
      });
      if (isJoined) {
        notify("info", i18n.t('events.left', 'Abgemeldet'), i18n.t('events.leftMsg', 'Du bist von «{{title}}» abgemeldet.', { title: eventTitle }));
      } else if (status === "pending") {
        notify("info", i18n.t('events.requested', 'Anfrage gesendet'), i18n.t('events.requestedMsg', 'Die Organisatoren bestätigen deine Anmeldung für «{{title}}».', { title: eventTitle }));
      } else if (status === "waitlisted") {
        notify("info", i18n.t('events.waitlisted', 'Auf der Warteliste'), i18n.t('events.waitlistedMsg', '«{{title}}» ist voll. Du rückst nach, sobald ein Platz frei wird.', { title: eventTitle }));
      } else {
        notify("success", i18n.t('events.joined', 'Angemeldet'), i18n.t('events.joinedMsg', 'Du bist für «{{title}}» angemeldet.', { title: eventTitle }));
      }
    },
    onError: (err) => {
      const msg =
        err instanceof Error ? err.message : i18n.t('events.attendanceFailed', 'Die Teilnahme konnte nicht gespeichert werden.');
      notify("error", "Error", msg);
    },
  });
}

/** "Vielleicht", or take it back when it is already the answer. */
export function useMaybeEvent() {
  const { notify } = useToast();
  const { currentUser } = useAuth();
  const events = useListCache<ClubEvent>(qk.events);

  return useMutation({
    mutationFn: async ({ eventId, eventTitle }: { eventId: string; eventTitle: string }) => {
      const ev = events.get()?.find((e) => e.id === eventId);
      const wasMaybe = ev?.myStatus === "maybe";
      if (wasMaybe) await leaveEvent(eventId, "");
      else await maybeEvent(eventId);
      return { eventId, eventTitle, wasMaybe };
    },
    onSuccess: ({ eventId, eventTitle, wasMaybe }) => {
      const me = currentUser?.id ?? "";
      events.patch(eventId, (ev) => ({
        ...ev,
        myStatus: wasMaybe ? null : "maybe",
        attendees: ev.attendees.filter((id) => id !== me),
      }));
      notify(
        "info",
        wasMaybe ? i18n.t("events.maybeRemoved", "Antwort zurückgezogen") : i18n.t("events.maybeSet", "Vielleicht"),
        wasMaybe
          ? i18n.t("events.maybeRemovedMsg", "Für «{{title}}» hast du keine Antwort mehr.", { title: eventTitle })
          : i18n.t("events.maybeSetMsg", "Du kommst vielleicht zu «{{title}}». Es ist kein Platz für dich reserviert.", { title: eventTitle }),
      );
    },
    onError: (err) => {
      notify("error", "Error", err instanceof Error ? err.message : i18n.t("events.attendanceFailed", "Die Teilnahme konnte nicht gespeichert werden."));
    },
  });
}
