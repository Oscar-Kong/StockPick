import { redirect } from "next/navigation";

type Props = { searchParams: Promise<{ symbol?: string }> };

export default async function AnalyzeRedirect({ searchParams }: Props) {
  const params = await searchParams;
  const sym = params.symbol?.trim();
  redirect(sym ? `/workspace?symbol=${encodeURIComponent(sym.toUpperCase())}` : "/workspace");
}
