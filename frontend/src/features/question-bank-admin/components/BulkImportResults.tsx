import type { BulkImportResponse } from "@/features/question-bank-admin/api/question-bank.api";

/** Makes the backend's partial-success contract (Phase 5) legible -- not
 * re-deciding it, just surfacing exactly what it already reported. */
export function BulkImportResults({ result }: { result: BulkImportResponse }) {
  const failedRows = result.results.filter((r) => r.status === "failed");

  return (
    <div>
      <p>
        {result.succeeded} of {result.total_rows} rows imported
        {result.failed > 0 && `, ${result.failed} failed`}
      </p>
      {failedRows.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Row</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {failedRows.map((row) => (
              <tr key={row.row_number}>
                <td>{row.row_number}</td>
                <td>{row.error}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
