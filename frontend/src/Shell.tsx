import { useState } from "react";
import { HodPages } from "./Hod";
import { Empty, Panel, btnGhost } from "./Shared";
import { StudentPages } from "./Student";
import { TeacherPages } from "./Teacher";
import type { Role, Store, Student, Teacher } from "./types";

const NAV: Record<Role, { id: string; label: string }[]> = {
  student: [
    { id: "dashboard", label: "Dashboard" }, { id: "upload", label: "Upload Certificate" },
    { id: "certs", label: "My Certificates" }, { id: "leaderboard", label: "Leaderboard" }, { id: "profile", label: "Profile" },
  ],
  teacher: [
    { id: "dashboard", label: "Dashboard" }, { id: "pending", label: "Pending Certificates" },
    { id: "approved", label: "Approved Certificates" }, { id: "students", label: "Students" }, { id: "leaderboard", label: "Leaderboard" },
  ],
  hod: [
    { id: "dashboard", label: "Dashboard" }, { id: "students", label: "Students" }, { id: "certs", label: "Certificates" },
    { id: "teachers", label: "Teacher Management" }, { id: "leaderboard", label: "Leaderboards" },
    { id: "scoring", label: "Scoring Rules" }, { id: "audit", label: "Audit Logs" },
  ],
};

export interface ShellProps {
  store: Store; role: Role; name: string; subtitle: string;
  student?: Student; teacher?: Teacher; advisor?: string | null; onLogout: () => void;
}

export default function Shell({ store, role, name, subtitle, student, teacher, advisor, onLogout }: ShellProps) {
  const [view, setView] = useState("dashboard");
  const unread = store.notifications.filter((n) => !n.read).length;
  const nav = [...NAV[role], { id: "notifications", label: unread ? `Notifications (${unread})` : "Notifications" }];

  return (
    <div className="min-h-full flex flex-col md:flex-row">
      <aside className="md:w-60 bg-brand-900 text-white md:min-h-screen">
        <div className="px-5 py-4 font-semibold border-b border-white/10">Certificate Portal</div>
        <nav className="p-2 flex md:flex-col gap-1 overflow-x-auto" aria-label="Main">
          {nav.map((n) => (
            <button key={n.id} onClick={() => setView(n.id)} aria-current={view === n.id ? "page" : undefined}
              className={`text-left px-3 py-2 rounded text-sm whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-white ${
                view === n.id ? "bg-brand-600" : "hover:bg-white/10"}`}>
              {n.label}
            </button>
          ))}
          <button onClick={onLogout}
            className="text-left px-3 py-2 rounded text-sm hover:bg-white/10 md:mt-6 focus:outline-none focus-visible:ring-2 focus-visible:ring-white">
            Logout
          </button>
        </nav>
      </aside>

      <div className="flex-1 min-w-0">
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex justify-between text-sm">
          <span className="font-medium text-brand-900">Welcome, {name}</span>
          <span className="text-gray-500">{subtitle}</span>
        </header>
        <main className="p-6">
          {view === "notifications" ? <Notifications store={store} /> : (
            <>
              {role === "student" && student && <StudentPages view={view} student={student} store={store} go={setView} advisor={advisor} />}
              {role === "teacher" && teacher && <TeacherPages view={view} teacher={teacher} store={store} go={setView} />}
              {role === "hod" && <HodPages view={view} store={store} actor={name} />}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function Notifications({ store }: { store: Store }) {
  const unread = store.notifications.some((n) => !n.read);
  return (
    <Panel title="Notifications">
      {store.notifications.length === 0 ? <Empty text="You have no notifications." /> : (
        <>
          {unread && <button className={`${btnGhost} mb-4`} onClick={() => store.markNotificationsRead()}>Mark all as read</button>}
          <ul className="divide-y divide-gray-100">
            {store.notifications.map((n) => (
              <li key={n.id} className="py-3 text-sm">
                <div className={n.read ? "text-gray-600" : "font-medium text-brand-900"}>{n.title}</div>
                {n.message && <div className="text-gray-500">{n.message}</div>}
                <div className="text-xs text-gray-400">{n.at}</div>
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}
