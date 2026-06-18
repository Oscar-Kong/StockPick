import { Suspense } from "react";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { PortfolioWorkspace } from "@/components/portfolio/PortfolioWorkspace";

function PortfolioPageInner() {
  return <PortfolioWorkspace />;
}

export default function PortfolioPage() {
  return (
    <Suspense fallback={<LoadingSkeleton variant="home" />}>
      <PortfolioPageInner />
    </Suspense>
  );
}
