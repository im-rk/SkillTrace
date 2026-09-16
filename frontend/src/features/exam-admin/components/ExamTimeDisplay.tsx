import { LOCAL_TIMEZONE } from "@/lib/timezone";

/** Always shown in the viewer's own local timezone, labeled explicitly --
 * the phase doc calls out unlabeled/ambiguous exam times as a common
 * instructor/student confusion source in scheduling UIs. */
export function ExamTimeDisplay({ iso }: { iso: string }) {
  return (
    <span>
      {new Date(iso).toLocaleString()} ({LOCAL_TIMEZONE})
    </span>
  );
}
