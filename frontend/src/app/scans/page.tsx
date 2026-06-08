import { redirect } from "next/navigation";

export default function ScansRedirect() {
  redirect("/library?tab=scans");
}
