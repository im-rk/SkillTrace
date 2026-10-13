import type { StudentMasteryRow } from "@/features/question-bank-admin/api/skills.api";
import { Chip } from "@/components/ui/Chip";
import { EmptyState, Meter } from "@/components/ui/Bits";
import { pct } from "@/lib/format";

/** Every student who has practised or been examined on the skill, with their current mastery. */
export function SkillStudents({ rows, threshold }: { rows: StudentMasteryRow[] | null; threshold: number }) {
  if (rows === null) return null;
  if (rows.length === 0)
    return (
      <div className="card">
        <EmptyState icon="users" title="No student has attempted this skill yet">
          As students practise or take an exam on this skill, their mastery appears here.
        </EmptyState>
      </div>
    );

  return (
    <div className="card table-wrap">
      <table className="table">
        <caption className="sr-only">Student mastery for this skill</caption>
        <thead>
          <tr>
            <th scope="col">Student</th>
            <th scope="col">Mastery</th>
            <th scope="col" className="right">
              Answers
            </th>
            <th scope="col">Mastered</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.student_id}>
              <td>
                <div style={{ fontWeight: 600 }}>{row.display_name}</div>
                <div className="muted small">{row.email}</div>
              </td>
              <td>
                <div className="bar-cell">
                  <Meter value={row.current_mastery} goal={threshold} label={`${row.display_name} mastery`} />
                  <span className="num">{pct(row.current_mastery)}%</span>
                </div>
              </td>
              <td className="right num">{row.total_attempts}</td>
              <td>{row.is_mastered ? <Chip tone="ok">Yes</Chip> : <Chip>Not yet</Chip>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
