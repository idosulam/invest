"use client";

import { X, AlertTriangle } from "lucide-react";

interface ConfirmationModalProps {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "default";
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export function ConfirmationModal({
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "danger",
  onConfirm,
  onCancel,
  loading = false,
}: ConfirmationModalProps) {
  const variantStyles = {
    danger: {
      icon: "bg-red-500/10 text-danger-500",
      button: "bg-danger-600 hover:bg-danger-700 text-white",
    },
    warning: {
      icon: "bg-amber-500/10 text-warning-500",
      button: "bg-warning-600 hover:bg-warning-700 text-white",
    },
    default: {
      icon: "bg-primary-500/10 text-primary-500",
      button: "bg-primary-600 hover:bg-primary-700 text-white",
    },
  };

  const styles = variantStyles[variant];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-surface-900 border border-surface-200 rounded-xl shadow-2xl w-full max-w-md mx-4">
        <div className="flex items-start gap-4 px-6 py-5">
          <div className={`p-2.5 rounded-lg ${styles.icon}`}>
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-white">{title}</h3>
            <p className="text-sm text-surface-500 mt-1.5">{message}</p>
          </div>
          <button
            onClick={onCancel}
            className="p-1 text-surface-400 hover:text-white rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex justify-end gap-2 px-6 py-4 border-t border-surface-200">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-surface-500 hover:text-white transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-50 ${styles.button}`}
          >
            {loading ? "Deleting..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
