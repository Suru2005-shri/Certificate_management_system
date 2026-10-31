import { useState } from "react";
import { CLASSES, POINTS } from "./data";
import { Card, CertTable, Empty, Leaderboard, Panel, Table, Td, btn, btnGhost, input } from "./Shared";
import type { ClassName, Store } from "./types";

export function HodPages({ view, store, actor }: { view: string; store: Store; actor: string }) {
  const [cls, setCls] = useState<"All" | ClassName>("All");
  const [form, setForm] = useState({ name: "", email: "", phone: "", cls: "SE" as ClassName, canAdjust: false });
  const [err, setErr] = useState("");
  const [code, setCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [bases, setBases] = useState<Record<string, string>>({});

  const guard = async (fn: () => Promise<unknown>) => {
    setErr(""); setBusy(true);
    try { await fn(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const inClass = (id: string) => cls === "All" || store.students.find((s) => s.id === id)?.cls === cls;
  const certs = store.certs.filter((c) => inClass(c.studentId));
  const errBox = err && <p role="alert" className="mb-3 text-sm text-red-700">{err}</p>;

  const filter = (
    <div className="mb-4 flex items-center gap-2 text-sm">
      <label htmlFor="cf">Class</label>
      <select id="cf" className={`${input} w-32`} value={cls} onChange={(e) => setCls(e.target.value as "All" | ClassName)}>
        <option>All</option>{CLASSES.map((c) => <option key={c}>{c}</option>)}
      </select>
    </div>
  );

  if (view === "students")
    return (
      <Panel title="Students">{filter}
        <Table head={["Name", "Roll No.", "Class", "Approved certificates"]}>
          {store.students.filter((s) => cls === "All" || s.cls === cls).map((s) => (
            <tr key={s.id}><Td>{s.name}</Td><Td>{s.roll}</Td><Td>{s.cls}</Td>
              <Td>{s.approvedCount ?? store.certs.filter((c) => c.studentId === s.id && c.status === "Approved").length}</Td></tr>
          ))}
        </Table>
      </Panel>
    );
  if (view === "certs") return <Panel title="All Certificates">{filter}<CertTable certs={certs} store={store} /></Panel>;
  if (view === "leaderboard")
    return <div className="space-y-6">{CLASSES.map((c) => <Leaderboard key={c} store={store} cls={c} />)}</div>;

  if (view === "teachers")
    return (
      <div className="space-y-6">
        <Panel title="Add Teacher">
          {errBox}
          <form className="grid sm:grid-cols-2 gap-3 max-w-2xl" onSubmit={(e) => {
            e.preventDefault();
            if (!form.name.trim() || !form.email.trim() || !form.phone.trim()) { setErr("Name, email and phone are required."); return; }
            guard(async () => { setCode(await store.addTeacher({ ...form, name: form.name.trim() }, actor));
              setForm({ ...form, name: "", email: "", phone: "" }); });
          }}>
            <div><label htmlFor="tn" className="block text-sm mb-1">Name</label>
              <input id="tn" className={input} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div><label htmlFor="te" className="block text-sm mb-1">Email</label>
              <input id="te" type="email" className={input} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div><label htmlFor="tp" className="block text-sm mb-1">Phone</label>
              <input id="tp" className={input} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
            <div><label htmlFor="tc" className="block text-sm mb-1">Class</label>
              <select id="tc" className={input} value={form.cls} onChange={(e) => setForm({ ...form, cls: e.target.value as ClassName })}>
                {CLASSES.map((c) => <option key={c}>{c}</option>)}</select></div>
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <input type="checkbox" checked={form.canAdjust} onChange={(e) => setForm({ ...form, canAdjust: e.target.checked })} />
              May change the monthly ranking (recorded in the audit log)
            </label>
            <div className="sm:col-span-2"><button className={btn} type="submit" disabled={busy}>Add teacher</button></div>
          </form>
          {code && (
            <div className="mt-4 text-sm bg-green-50 border border-green-200 rounded p-3 max-w-2xl">
              Access code (shown once, valid 72 hours, single use): <strong className="font-mono">{code}</strong>
              <p className="text-xs text-gray-600 mt-1">Give it to the teacher privately. They sign in with the same email and enter this code with their phone number.</p>
            </div>
          )}
        </Panel>
        <Panel title="Teachers">
          {store.teachers.length === 0 ? <Empty text="No teachers yet." /> : (
            <Table head={["Name", "Class", "Status", ""]}>
              {store.teachers.map((t) => (
                <tr key={t.id}>
                  <Td>{t.name}</Td>
                  <Td>
                    <select aria-label={`Class for ${t.name}`} className={`${input} w-28`} value={t.cls ?? ""}
                      onChange={(e) => guard(() => store.assignTeacher(t.id, e.target.value as ClassName, actor))}>
                      {!t.cls && <option value="">Unassigned</option>}
                      {CLASSES.map((c) => <option key={c}>{c}</option>)}
                    </select>
                  </Td>
                  <Td>{t.active ? "Active" : "Deactivated"}</Td>
                  <Td><button className={btnGhost} disabled={busy} onClick={() => guard(() => store.setTeacherActive(t.id, !t.active, actor))}>
                    {t.active ? "Deactivate" : "Activate"}</button></Td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>
      </div>
    );
  if (view === "scoring")
    return (
      <Panel title="Scoring Rules">
        {errBox}
        {store.rules.length > 0 ? (
          <Table head={["Category", "Base points", ""]}>
            {store.rules.map((r) => (
              <tr key={r.id}>
                <Td>{r.category.charAt(0).toUpperCase() + r.category.slice(1)}</Td>
                <Td><input aria-label={`Points for ${r.category}`} type="number" min={0} max={100} className={`${input} w-24`}
                  value={bases[r.id] ?? String(r.base)} onChange={(e) => setBases({ ...bases, [r.id]: e.target.value })} /></Td>
                <Td><button className={btnGhost} disabled={busy || bases[r.id] === undefined || Number(bases[r.id]) === r.base}
                  onClick={() => guard(async () => { await store.updateRule(r.id, Number(bases[r.id])); setBases(({ [r.id]: _done, ...rest }) => rest); })}>Save</button></Td>
              </tr>
            ))}
          </Table>
        ) : (
          <Table head={["Category", "Base points"]}>
            {Object.entries(POINTS).map(([k, v]) => <tr key={k}><Td>{k}</Td><Td>{v}</Td></tr>)}
          </Table>
        )}
        <p className="text-xs text-gray-500 mt-3">Bonuses: Sports by level, Hackathon with prize. Changes apply to future approvals and are audited.</p>
      </Panel>
    );
  if (view === "audit")
    return (
      <Panel title="Audit Logs">
        {store.audit.length === 0 ? <Empty text="No activity recorded yet." /> : (
          <Table head={["Time", "Actor", "Action", "Target"]}>
            {store.audit.map((a, i) => <tr key={i}><Td>{a.at}</Td><Td>{a.actor}</Td><Td>{a.action}</Td><Td>{a.target}</Td></tr>)}
          </Table>
        )}
      </Panel>
    );

  const st = store.stats;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card title="Total Students" value={st?.participating ?? store.students.length} />
        <Card title="Certificates (loaded)" value={store.certs.length} />
        <Card title="Pending" value={st?.pending ?? store.certs.filter((c) => c.status === "Pending").length} />
        <Card title="Approved" value={st?.approved ?? store.certs.filter((c) => c.status === "Approved").length} />
      </div>
      <Panel title="Recent submissions"><CertTable certs={store.certs.slice(0, 8)} store={store} /></Panel>
    </div>
  );
}
