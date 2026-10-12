import { PageHeader } from "@/components/page-header";

export default function Page() {
  return (
    <>
      <PageHeader title="Evidence Ledger" subtitle="Hash-chained, tamper-evident record of every decision." />
      <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
        Coming in a later milestone.
      </div>
    </>
  );
}
