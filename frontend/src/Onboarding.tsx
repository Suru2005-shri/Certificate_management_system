import { useEffect, useState } from "react";
import { api } from "./api";
import { btn, input } from "./Shared";
import type { ClassName } from "./types";

interface ClassRow { class_name: ClassName; advisor: string | null }
interface Dept { code: string; name: string; classes: ClassRow[] }

/** First sign-in after Keycloak: students create their profile, teachers activate with the HOD's access code. */
export default function Onboarding({ defaultName, onDone, onLogout }: {
  defaultName: string; onDone: () => void; onLogout: () => void;
}) {
  const [mode, setMode] = useState<"student" | "teacher">("student");
  const [depts, setDepts] = useState<Dept[]>([]);
  const [form, setForm] = useState({ full_name: defaultName, roll_no: "", department: "IT", class_name: "SE" as ClassName, phone: "", access_code: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get<Dept[]>("/departments").then(setDepts).catch(() => undefined); }, []);
  const dept = depts.find((d) => d.code === form.department);
  const advisor = dept?.classes.find((c) => c.class_name === form.class_name)?.advisor;
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      if (mode === "student")
        await api.post("/profile/register", {
          full_name: form.full_name, roll_no: form.roll_no, department: form.department, class_name: form.class_name, phone: form.phone });
      else await api.post("/auth/teacher-activate", { phone: form.phone, access_code: form.access_code });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-full flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-lg border border-gray-200 p-8">
        <h1 className="text-xl font-semibold text-brand-900 text-center">Complete your registration</h1>
        <p className="text-sm text-gray-500 text-center mb-6">Certificate &amp; Involvement Portal</p>

        <div role="tablist" className="grid grid-cols-2 gap-1 bg-gray-100 p-1 rounded-md mb-6">
          {(["student", "teacher"] as const).map((m) => (
            <button key={m} role="tab" aria-selected={mode === m} onClick={() => { setMode(m); setError(""); }}
              className={`py-2 text-sm rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 ${
                mode === m ? "bg-white text-brand-700 font-medium shadow-sm" : "text-gray-600"}`}>
              {m === "student" ? "I am a student" : "I am a teacher"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-4">
          {mode === "student" ? (
            <>
              <div><label htmlFor="fn" className="block text-sm mb-1">Full name</label>
                <input id="fn" className={input} required value={form.full_name} onChange={(e) => set("full_name", e.target.value)} /></div>
              <div><label htmlFor="rn" className="block text-sm mb-1">Roll number</label>
                <input id="rn" className={input} required value={form.roll_no} onChange={(e) => set("roll_no", e.target.value)} /></div>
              <div><label htmlFor="dp" className="block text-sm mb-1">Department</label>
                <select id="dp" className={input} value={form.department} onChange={(e) => set("department", e.target.value)}>
                  {(depts.length ? depts : [{ code: "IT", name: "Information Technology", classes: [] }]).map((d) =>
                    <option key={d.code} value={d.code}>{d.name}</option>)}</select></div>
              <div><label htmlFor="cl" className="block text-sm mb-1">Class</label>
                <select id="cl" className={input} value={form.class_name} onChange={(e) => set("class_name", e.target.value)}>
                  {["SE", "TE", "BE"].map((c) => <option key={c}>{c}</option>)}</select></div>
              <p className="text-sm text-gray-600">Department: {form.department} · Class Advisor: <strong>{advisor ?? "To be assigned by the HOD"}</strong></p>
            </>
          ) : (
            <div><label htmlFor="ac" className="block text-sm mb-1">Access code from the HOD</label>
              <input id="ac" className={input} required autoComplete="off" value={form.access_code} onChange={(e) => set("access_code", e.target.value)} /></div>
          )}
          <div><label htmlFor="ph" className="block text-sm mb-1">Phone number</label>
            <input id="ph" type="tel" className={input} required value={form.phone} onChange={(e) => set("phone", e.target.value)} /></div>

          {error && <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">{error}</p>}
          <button className={`${btn} w-full`} type="submit" disabled={busy}>{busy ? "Please wait…" : "Continue"}</button>
          <button type="button" className="w-full text-sm text-gray-500 underline" onClick={onLogout}>Sign out</button>
        </form>
      </div>
    </main>
  );
}
