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
        "bg-surface-100 rounded-lg border border-surface-300",
        paddings[padding],
        onClick && "cursor-pointer hover:border-surface-400 transition-colors",
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
  return <h3 className="text-base font-semibold text-surface-800">{children}</h3>;
}
