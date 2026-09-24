import type { ItemAnalysisRow } from "@/features/exam-results/api/results.api";

const pct = (value: number) => `${Math.round(value * 100)}%`;

function DiscriminationCell({ value }: { value: number | null }) {
  if (value === null) return <td>— (too few students)</td>;
  // Conventional psychometric bands: >= 0.4 strong, >= 0.2 acceptable, below that weak/negative.
  const label = value < 0 ? "negative — review this question" : value < 0.2 ? "weak" : value < 0.4 ? "acceptable" : "strong";
  return (
    <td>
      {value.toFixed(2)} ({label})
    </td>
  );
}

/** Per-question difficulty (p-value) and discrimination -- the classic psychometric
 * technique for spotting a question that's miscalibrated or not actually testing
 * the material (see backend/app/modules/results/item_analysis.py). */
export function ItemAnalysisTable({ items }: { items: ItemAnalysisRow[] }) {
  if (items.length === 0) return <p>No graded answers yet for this exam.</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>Question</th>
          <th>Answered by</th>
          <th>Difficulty (p-value)</th>
          <th>Discrimination</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.question_id}>
            <td>{item.prompt}</td>
            <td>{item.sample_size}</td>
            <td>{item.p_value === null ? "—" : pct(item.p_value)}</td>
            <DiscriminationCell value={item.discrimination} />
          </tr>
        ))}
      </tbody>
    </table>
  );
}
