import { redirect } from "next/navigation";

export default function MediumRedirect() {
  redirect("/scan?bucket=penny");
}
