import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { RedeemCodeForm } from "@/features/enrollment/components/RedeemCodeForm";
import { PageHeader } from "@/components/ui/PageHeader";

export default function EnrollPage() {
  return (
    <RequireAuth>
      <main className="narrow">
        <PageHeader eyebrow="Exams" title="Join an exam" lede="Enter the access code your instructor shared. You will go straight to the exam." />
        <div className="card card-pad">
          <RedeemCodeForm />
        </div>
      </main>
    </RequireAuth>
  );
}
