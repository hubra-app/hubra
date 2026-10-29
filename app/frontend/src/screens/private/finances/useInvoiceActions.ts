import { useMutation, useQueryClient } from "@tanstack/react-query";
import i18n from "i18next";
import { useToast, useNav } from "@/context/AppContext";
import { qk } from "@/data/keys";
import type { Invoice } from "@/types";
import {
  updateInvoice,
  deleteInvoice as apiDeleteInvoice,
  sendInvoiceReminder as apiSendReminder,
} from "@/api/finance";
import { formatDateTime } from "@/format";

export function useMarkInvoicePaid() {
  const { notify } = useToast();
  const { setSelectedInvoice } = useNav();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => updateInvoice(id, { status: "Paid" }),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: qk.invoices.all });
      const prev = queryClient.getQueryData<Invoice[]>(qk.invoices.all);
      queryClient.setQueryData<Invoice[]>(qk.invoices.all, (old) =>
        old?.map((inv) =>
          inv.id === id ? { ...inv, status: "Paid" as const } : inv,
        ),
      );
      setSelectedInvoice((prev) =>
        prev?.id === id ? { ...prev, status: "Paid" as const } : prev,
      );
      queryClient.setQueryData<Invoice>(qk.invoices.one(id), (old) =>
        old ? { ...old, status: "Paid" as const } : old,
      );
      return { prev };
    },
    onError: (err, _id, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(qk.invoices.all, ctx.prev);
      setSelectedInvoice((prev) =>
        prev?.id === _id ? { ...prev, status: "Open" as const } : prev,
      );
      queryClient.invalidateQueries({ queryKey: qk.invoices.one(_id) });
      const msg =
        err instanceof Error ? err.message : i18n.t('finance.invoiceUpdateFailed', 'Die Rechnung konnte nicht aktualisiert werden.');
      notify("error", i18n.t('common.error', 'Fehler'), msg);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: qk.dashboard });
    },
    onSuccess: () => {
      notify("success", i18n.t('finance.invoicePaid', 'Rechnung bezahlt'), i18n.t('finance.invoicePaidMsg', 'Die Rechnung ist als bezahlt markiert.'));
    },
  });
}

export function useSendInvoiceReminder() {
  const { notify } = useToast();
  const { setSelectedInvoice } = useNav();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiSendReminder(id),
    onSuccess: (data, id) => {
      const ts = data?.remindedAt
        ? formatDateTime(data.remindedAt)
        : formatDateTime(new Date());
      queryClient.setQueryData<Invoice[]>(qk.invoices.all, (prev) =>
        prev?.map((inv) =>
          inv.id === id
            ? { ...inv, reminderSentAt: [...(inv.reminderSentAt ?? []), ts] }
            : inv,
        ),
      );
      setSelectedInvoice((prev) =>
        prev?.id === id
          ? { ...prev, reminderSentAt: [...(prev.reminderSentAt ?? []), ts] }
          : prev,
      );
      notify("success", i18n.t('finance.reminderSent', 'Erinnerung gesendet'), i18n.t('finance.reminderSentMsg', 'Die Zahlungserinnerung wurde per E-Mail verschickt.'));
    },
    onError: (err) => {
      const msg =
        err instanceof Error ? err.message : i18n.t('finance.reminderFailed', 'Die Erinnerung konnte nicht gesendet werden.');
      notify("error", i18n.t('common.error', 'Fehler'), msg);
    },
  });
}

export function useDeleteInvoice() {
  const { notify } = useToast();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiDeleteInvoice(id),
    onMutate: (id) => {
      const prev = queryClient.getQueryData<Invoice[]>(qk.invoices.all) ?? [];
      queryClient.setQueryData<Invoice[]>(qk.invoices.all, (old) =>
        old?.filter((inv) => inv.id !== id),
      );
      return { prev };
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: qk.dashboard });
    },
    onError: (err, _id, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(qk.invoices.all, ctx.prev);
      const msg =
        err instanceof Error ? err.message : i18n.t('finance.invoiceDeleteFailed', 'Die Rechnung konnte nicht gelöscht werden.');
      notify("error", i18n.t('common.error', 'Fehler'), msg);
    },
    onSuccess: () => {
      notify("info", i18n.t('finance.invoice.deleted', 'Rechnung gelöscht.'), i18n.t('finance.invoice.deletedMsg', 'Die Rechnung wurde gelöscht.'));
    },
  });
}
