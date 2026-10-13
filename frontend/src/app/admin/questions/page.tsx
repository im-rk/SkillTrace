"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** The question bank now lives inside each skill; this keeps old links working. */
export default function QuestionBankRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/admin/skills");
  }, [router]);
  return null;
}
