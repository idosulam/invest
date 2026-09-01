import { clsx } from "clsx";
import { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: "sm" | "md" | "lg";
  onClick?: () => void;
}

export function Card({ children, className, padding = "md" }: CardProps) {
  const paddings = { sm: "p-3", md: "p-4", lg: "p-6" };
  return (
    <div
      className={clsx(
        "bg-white rounded-xl border border-surface-200 shadow-sm",
        paddings[padding],
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex items-center justify-between mb-4", className)}>
      {children}
    </div>
  );
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <h3 className="text-lg font-semibold text-surface-900">{children}</h3>;
}
