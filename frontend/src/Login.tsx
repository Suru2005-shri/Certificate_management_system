import { useState } from "react";
import { ADVISORS, CLASSES } from "./data";
import { btn, input } from "./Shared";
import type { ClassName, Role, Session, Store } from "./types";

const tabs: { id: Role; label: string }[] = [
  { id: "student", label: "Student" }, { id: "teacher", label: "Teacher" }, { id: "hod", label: "HOD" },
];

// Demo sign-in. In production this redirects to Keycloak; the advisor shown comes from
// class-assignment data, never from user input.
export default function Login({ store, onLogin }: { store: Store; onLogin: (s: Session) => void }) {
  const [role, setRole] = useState<Role>("student");
  const [studentId, setStudentId] = useState(store.students[0].id);
  const [teacherId, setTeacherId] = useState(store.teachers[0].id);
  const [cls, setCls] = useState<ClassName>("SE");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onLogin(role === "hod" ? { role, id: "hod" } : role === "student" ? { role, id: studentId } : { role, id: teacherId });
  };

  return (
    <main className="min-h-full flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-lg border border-gray-200 p-8">
        <h1 className="text-xl font-semibold text-brand-900 text-center">Student Certificate &amp; Involvement Portal</h1>
        <p className="text-sm text-gray-500 text-center mb-6">Department of Information Technology</p>

        <div role="tablist" className="grid grid-cols-3 gap-1 bg-gray-100 p-1 rounded-md mb-6">
          {tabs.map((t) => (
            <button key={t.id} role="tab" aria-selected={role === t.id} onClick={() => setRole(t.id)}
              className={`py-2 text-sm rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 ${
                role === t.id ? "bg-white text-brand-700 font-medium shadow-sm" : "text-gray-600"}`}>
              {t.label}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-4">
          {role === "student" && (
            <>
              <div><label htmlFor="stu" className="block text-sm mb-1">Demo student</label>
                <select id="stu" className={input} value={studentId} onChange={(e) => {
                  setStudentId(e.target.value);
                  setCls(store.students.find((s) => s.id === e.target.value)!.cls);
                }}>
                  {store.students.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.cls})</option>)}
                </select></div>
              <p className="text-sm text-gray-600">
                Class Advisor: <strong>{ADVISORS[store.students.find((s) => s.id === studentId)!.cls]}</strong>
              </p>
            </>
          )}
          {role === "teacher" && (
            <div><label htmlFor="tea" className="block text-sm mb-1">Demo teacher</label>
              <select id="tea" className={input} value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
                {store.teachers.filter((t) => t.active).map((t) => <option key={t.id} value={t.id}>{t.name} ({t.cls})</option>)}
              </select></div>
          )}
          {role === "hod" && <p className="text-sm text-gray-600">Department-wide access (SE, TE, BE).</p>}
          <button className={`${btn} w-full`} type="submit">Sign in</button>
        </form>
        <p className="mt-4 text-xs text-gray-400 text-center">Demo mode – sample data, nothing is saved. {CLASSES.length} classes loaded.</p>
      </div>
    </main>
  );
}
