import { redirect } from "next/navigation";

export default function PennyRedirect() {
  redirect("/scan?bucket=penny");
}
