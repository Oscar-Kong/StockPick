import { redirect } from "next/navigation";

export default function CompounderRedirect() {
  redirect("/scan?bucket=compounder");
}
