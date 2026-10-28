import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast, useNav, useData } from "@/context/AppContext";
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
  const { setOpenInvoiceCount } = useData();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => updateInvoice(id, { status: "Paid" }),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ["invoices"] });
      const prev = queryClient.getQueryData<Invoice[]>(["invoices"]);
      queryClient.setQueryData<Invoice[]>(["invoices"], (old) =>
        old?.map((inv) =>
          inv.id === id ? { ...inv, status: "Paid" as const } : inv,
        ),
      );
      setSelectedInvoice((prev) =>
        prev?.id === id ? { ...prev, status: "Paid" as const } : prev,
      );
      setOpenInvoiceCount((c) => Math.max(0, c - 1));
      return { prev };
    },
    onError: (err, _id, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(["invoices"], ctx.prev);
      setSelectedInvoice((prev) =>
        prev?.id === _id ? { ...prev, status: "Open" as const } : prev,
      );
      setOpenInvoiceCount((c) => c + 1);
      const msg =
        err instanceof Error ? err.message : "Could not update invoice.";
      notify("error", "Error", msg);
    },
    onSuccess: () => {
      notify("success", "Invoice paid", "Invoice marked as paid.");
    },
  });
}

export function useSendInvoiceReminder() {
  const { notify } = useToast();
  const { setInvoices } = useData();
  const { setSelectedInvoice } = useNav();

  return useMutation({
    mutationFn: (id: string) => apiSendReminder(id),
    onSuccess: (data, id) => {
      const ts = data?.remindedAt
        ? formatDateTime(data.remindedAt)
        : formatDateTime(new Date());
      setInvoices((prev) =>
        prev.map((inv) =>
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
      notify("success", "Reminder sent", "Payment reminder email dispatched.");
    },
    onError: (err) => {
      const msg =
        err instanceof Error ? err.message : "Could not send reminder.";
      notify("error", "Error", msg);
    },
  });
}

export function useDeleteInvoice() {
  const { notify } = useToast();
  const { setOpenInvoiceCount } = useData();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiDeleteInvoice(id),
    onMutate: (id) => {
      const prev = queryClient.getQueryData<Invoice[]>(["invoices"]) ?? [];
      const invoice = prev.find((inv) => inv.id === id);
      queryClient.setQueryData<Invoice[]>(["invoices"], (old) =>
        old?.filter((inv) => inv.id !== id),
      );
      if (invoice && invoice.status !== "Paid") {
        setOpenInvoiceCount((c) => Math.max(0, c - 1));
      }
      return { prev };
    },
    onError: (err, _id, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(["invoices"], ctx.prev);
      const msg =
        err instanceof Error ? err.message : "Could not delete invoice.";
      notify("error", "Error", msg);
    },
  });
}
