"use client";

import clsx from "clsx";
import { LoadingSkeleton } from "./LoadingSkeleton";

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

export function DenseTableLoadingRows({
  columns,
  rows = 5,
  className,
}: {
  columns: number;
  rows?: number;
  className?: string;
}) {
  return (
    <tbody className={className} aria-hidden>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={rowIndex} className="dense-table__loading-row">
          {Array.from({ length: columns }).map((__, colIndex) => (
            <td key={colIndex}>
              <LoadingSkeleton lines={1} className="py-1" />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}

export function DenseTableEmptyRow({
  colSpan,
  message,
  action,
  className,
}: {
  colSpan: number;
  message: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <tbody className={className}>
      <tr>
        <td colSpan={colSpan} className="dense-table__empty-cell">
          <p className="text-sm text-tertiary">{message}</p>
          {action && <div className="mt-3">{action}</div>}
        </td>
      </tr>
    </tbody>
  );
}

export function DenseTableNumericCell({
  children,
  className,
  title,
}: {
  children: React.ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <td className={clsx("col-num finance-value", className)} title={title}>
      {children}
    </td>
  );
}

export function DenseTableRow({
  selected,
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLTableRowElement> & { selected?: boolean }) {
  return (
    <tr
      className={clsx(selected && "is-selected", className)}
      data-selected={selected ? "true" : undefined}
      {...props}
    >
      {children}
    </tr>
  );
}
