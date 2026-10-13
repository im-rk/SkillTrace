import type { ItemAnalysisRow } from "@/features/exam-results/api/results.api";
import { Chip } from "@/components/ui/Chip";
import { EmptyState, Meter } from "@/components/ui/Bits";

const pct = (value: number) => `${Math.round(value * 100)}%`;

function Discrimination({ value }: { value: number | null }) {
  if (value === null) return <span className="muted">— (too few students)</span>;
  // Conventional psychometric bands: >= 0.4 strong, >= 0.2 acceptable, below that weak, negative = review.
  const [tone, label] = value < 0 ? (["bad", "negative — review this question"] as const) : value < 0.2 ? (["warn", "weak"] as const) : value < 0.4 ? (["info", "acceptable"] as const) : (["ok", "strong"] as const);
  return (
    <span className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
      <span className="num" style={{ fontWeight: 650 }}>
        {value.toFixed(2)}
      </span>
      <Chip tone={tone} dot={false}>
        {label}
      </Chip>
    </span>
  );
}

/** Per-question difficulty (p-value) and discrimination: the classic way to spot a question that is miscalibrated or
 * does not actually separate students who know the material from those who do not. */
export function ItemAnalysisTable({ items }: { items: ItemAnalysisRow[] }) {
  if (items.length === 0)
    return (
      <EmptyState icon="chart" title="No graded answers yet">
        Item analysis appears once students have submitted answers.
      </EmptyState>
    );

  return (
    <div className="table-wrap">
      <table className="table">
        <caption className="sr-only">Difficulty and discrimination of each question</caption>
        <thead>
          <tr>
            <th scope="col">Question</th>
            <th scope="col" className="right">
              Answered by
            </th>
            <th scope="col">Got it right</th>
            <th scope="col">Discrimination</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.question_id}>
              <td style={{ maxWidth: 360 }}>{item.prompt}</td>
              <td className="right num">{item.sample_size}</td>
              <td>
                {item.p_value === null ? (
                  "—"
                ) : (
                  <div className="bar-cell">
                    <Meter value={item.p_value} label={`${item.prompt} difficulty`} />
                    <span className="num">{pct(item.p_value)}</span>
                  </div>
                )}
              </td>
              <td>
                <Discrimination value={item.discrimination} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
