import { redirect } from "next/navigation";

export default function TradesRedirect() {
  redirect("/workspace?tab=journal");
}
