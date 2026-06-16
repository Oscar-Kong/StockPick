"use client";

import clsx from "clsx";

interface DenseTableProps {
  children: React.ReactNode;
  className?: string;
  caption?: string;
  stickyHeader?: boolean;
}

export function DenseTable({ children, className, caption, stickyHeader = true }: DenseTableProps) {
  return (
    <div className={clsx("dense-table-wrap", className)}>
      <table className={clsx("dense-table", stickyHeader && "dense-table--sticky")}>
        {caption && <caption className="sr-only">{caption}</caption>}
        {children}
      </table>
    </div>
  );
}

export function DenseTableToolbar({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("dense-table-toolbar", className)}>{children}</div>;
}
