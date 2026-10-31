import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import { accountName, initAuth, logout } from "./auth";
import Onboarding from "./Onboarding";
import { useRemoteStore, type Me } from "./remote";
import Shell from "./Shell";
import { btn } from "./Shared";
import type { Student, Teacher } from "./types";

type State =
  | { phase: "loading" }
  | { phase: "onboard" }
  | { phase: "blocked"; message: string }
  | { phase: "ready"; me: Me };

export default function RemoteApp() {
  const [state, setState] = useState<State>({ phase: "loading" });

  const load = useCallback(async () => {
    try {
      await initAuth();            // redirects to the Keycloak login page if not signed in
      setState({ phase: "ready", me: await api.get<Me>("/me") });
    } catch (e) {
      if (e instanceof ApiError && e.status === 403 && /not registered/i.test(e.message)) setState({ phase: "onboard" });
      else setState({ phase: "blocked", message: (e as Error).message || "Could not sign you in." });
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  if (state.phase === "loading")
    return <p className="p-8 text-center text-gray-500" role="status">Loading…</p>;
  if (state.phase === "onboard")
    return <Onboarding defaultName={accountName()} onDone={load} onLogout={logout} />;
  if (state.phase === "blocked")
    return (
      <main className="min-h-full flex items-center justify-center p-4">
        <div className="bg-white border border-gray-200 rounded-lg p-8 max-w-md text-center space-y-4">
          <p role="alert" className="text-sm text-gray-700">{state.message}</p>
          <div className="flex gap-2 justify-center">
            <button className={btn} onClick={() => { setState({ phase: "loading" }); void load(); }}>Try again</button>
            <button className="border border-gray-300 rounded-md px-4 py-2 text-sm" onClick={logout}>Sign out</button>
          </div>
        </div>
      </main>
    );
  return <Ready me={state.me} />;
}

function Ready({ me }: { me: Me }) {
  const store = useRemoteStore(me);
  const student: Student | undefined = me.role === "student"
    ? { id: me.id, name: me.full_name, roll: me.roll_no ?? "", cls: me.class_name ?? "SE" } : undefined;
  const teacher: Teacher | undefined = me.role === "teacher"
    ? { id: me.id, name: me.full_name, cls: me.class_name, active: true } : undefined;
  return (
    <Shell
      store={store} role={me.role} student={student} teacher={teacher} advisor={me.advisor}
      name={me.full_name}
      subtitle={me.role === "student" ? `${me.class_name} · ${me.department}` : me.role === "teacher" ? `Class ${me.class_name}` : `${me.department_name} Department`}
      onLogout={logout}
    />
  );
}
