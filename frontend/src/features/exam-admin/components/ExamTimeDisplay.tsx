import { formatWindow } from "@/lib/format";
import { LOCAL_TIMEZONE } from "@/lib/timezone";

/** Always shown in the viewer's own timezone, labelled explicitly: an unlabelled exam time is a classic source
 * of instructor/student confusion. */
export function ExamWindow({ start, end }: { start: string; end: string }) {
  return (
    <span>
      {formatWindow(start, end)} ({LOCAL_TIMEZONE})
    </span>
  );
}
