"use client";

import { AlertTriangle, LoaderCircle, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export type ConfirmDialogState = {
  title: string;
  description: string;
  subject?: string;
  confirmLabel?: string;
  onConfirm: () => void;
};

export function ConfirmDialog({
  dialog,
  busy = false,
  onClose,
}: {
  dialog: ConfirmDialogState | null;
  busy?: boolean;
  onClose: () => void;
}) {
  if (!dialog) return null;
  return (
    <div
      className="confirm-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <section
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-description"
      >
        <header>
          <span>
            <AlertTriangle />
          </span>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label="Close confirmation"
          >
            <X />
          </button>
        </header>
        <div>
          <span className="confirm-kicker">CONFIRM PERMANENT DELETION</span>
          <h2 id="confirm-title">{dialog.title}</h2>
          {dialog.subject && (
            <strong className="confirm-subject">{dialog.subject}</strong>
          )}
          <p id="confirm-description">{dialog.description}</p>
        </div>
        <footer>
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={busy}
          >
            Keep it
          </Button>
          <Button
            type="button"
            className="confirm-delete"
            onClick={dialog.onConfirm}
            disabled={busy}
          >
            {busy ? <LoaderCircle className="spin" /> : <Trash2 />}
            {dialog.confirmLabel || "Delete permanently"}
          </Button>
        </footer>
      </section>
    </div>
  );
}
