import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { RedeemCodeForm } from "@/features/enrollment/components/RedeemCodeForm";

export default function EnrollPage() {
  return (
    <RequireAuth>
      <main>
        <h1>Join an exam</h1>
        <RedeemCodeForm />
      </main>
    </RequireAuth>
  );
}
