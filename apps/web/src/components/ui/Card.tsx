import { clsx } from "clsx";
import { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: "sm" | "md" | "lg";
  onClick?: () => void;
}

export function Card({ children, className, padding = "md", onClick }: CardProps) {
  const paddings = { sm: "p-3", md: "p-4", lg: "p-6" };
  return (
    <div
      onClick={onClick}
      className={clsx(
        "bg-surface-800 rounded-xl border border-surface-200 shadow-sm",
        paddings[padding],
        onClick && "cursor-pointer",
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
  return <h3 className="text-lg font-semibold text-white">{children}</h3>;
}
