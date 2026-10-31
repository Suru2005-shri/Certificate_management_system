import { useState } from "react";
import Login from "./Login";
import Shell from "./Shell";
import { useDemoStore } from "./store";
import type { Session } from "./types";

/** Demo mode (npm run dev:demo): sample data, no servers needed. */
export default function DemoApp() {
  const store = useDemoStore();
  const [session, setSession] = useState<Session | null>(null);
  if (!session) return <Login store={store} onLogin={setSession} />;

  const student = session.role === "student" ? store.students.find((s) => s.id === session.id) : undefined;
  const teacher = session.role === "teacher" ? store.teachers.find((t) => t.id === session.id) : undefined;
  return (
    <Shell
      key={session.role + session.id}
      store={store} role={session.role} student={student} teacher={teacher}
      name={student?.name ?? teacher?.name ?? "HOD"}
      subtitle={student ? `${student.cls} · IT` : teacher ? `Class ${teacher.cls}` : "IT Department"}
      onLogout={() => setSession(null)}
    />
  );
}
