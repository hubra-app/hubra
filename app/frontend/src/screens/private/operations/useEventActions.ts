import i18n from "i18next";
import { useMutation } from "@tanstack/react-query";
import { useToast, useAuth, useData } from "@/context/AppContext";
import { joinEvent, leaveEvent } from "@/api/events";

export function useToggleJoinEvent() {
  const { notify } = useToast();
  const { currentUser } = useAuth();
  const { myJoinedEvents, setEvents } = useData();

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
      const isJoined = myJoinedEvents.has(eventId);
      if (isJoined) {
        await leaveEvent(eventId, memberId);
      } else {
        await joinEvent(eventId, memberId);
      }
      return { isJoined, eventTitle };
    },
    onMutate: ({ eventId }) => {
      const isJoined = myJoinedEvents.has(eventId);
      if (currentUser) {
        setEvents((prev) =>
          prev.map((ev) =>
            ev.id !== eventId
              ? ev
              : {
                  ...ev,
                  attendees: isJoined
                    ? ev.attendees.filter((id) => id !== currentUser.id)
                    : [...ev.attendees, currentUser.id],
                },
          ),
        );
      }
      return { isJoined };
    },
    onError: (err, { eventId }, ctx) => {
      const isJoined = ctx?.isJoined ?? false;
      if (currentUser) {
        setEvents((prev) =>
          prev.map((ev) =>
            ev.id !== eventId
              ? ev
              : {
                  ...ev,
                  attendees: isJoined
                    ? [...ev.attendees, currentUser.id]
                    : ev.attendees.filter((id) => id !== currentUser.id),
                },
          ),
        );
      }
      const msg =
        err instanceof Error ? err.message : i18n.t('events.attendanceFailed', 'Die Teilnahme konnte nicht gespeichert werden.');
      notify("error", "Error", msg);
    },
    onSuccess: ({ isJoined, eventTitle }) => {
      if (isJoined) {
        notify("info", i18n.t('events.left', 'Abgemeldet'), i18n.t('events.leftMsg', 'Du bist von «{{title}}» abgemeldet.', { title: eventTitle }));
      } else {
        notify("success", i18n.t('events.joined', 'Angemeldet'), i18n.t('events.joinedMsg', 'Du bist für «{{title}}» angemeldet.', { title: eventTitle }));
      }
    },
  });
}
