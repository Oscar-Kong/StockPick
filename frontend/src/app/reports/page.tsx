import { redirect } from "next/navigation";

export default function ReportsRedirect() {
  redirect("/library?tab=reports");
}
