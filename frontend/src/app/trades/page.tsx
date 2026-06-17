import { redirect } from "next/navigation";

export default function TradesRedirect() {
  redirect("/?journal=1#home-journal");
}
