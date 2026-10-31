import { useCallback, useEffect, useState, type ReactNode } from "react";
import type { Cert, ClassName, Leaderboard as LB, Status, Store } from "./types";

export const btn =
  "bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-md text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-600 disabled:opacity-50";
export const btnGhost =
  "border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-md text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600";
export const input =
  "w-full border border-gray-300 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-600";

const badgeColor: Record<Status, string> = {
  Pending: "bg-amber-50 text-amber-800 border-amber-200",
  "Under Review": "bg-blue-50 text-blue-800 border-blue-200",
  Approved: "bg-green-50 text-green-800 border-green-200",
  Rejected: "bg-red-50 text-red-800 border-red-200",
  "Resubmission Required": "bg-orange-50 text-orange-800 border-orange-200",
};
export const Badge = ({ status }: { status: Status }) => (
  <span className={`inline-block text-xs px-2 py-0.5 rounded border ${badgeColor[status]}`}>{status}</span>
);

export const Card = ({ title, value }: { title: string; value: ReactNode }) => (
  <div className="bg-white border border-gray-200 rounded-lg p-4">
    <div className="text-sm text-gray-500">{title}</div>
    <div className="text-2xl font-semibold text-brand-900 mt-1">{value}</div>
  </div>
);

export const Panel = ({ title, children }: { title?: string; children: ReactNode }) => (
  <section className="bg-white border border-gray-200 rounded-lg p-5">
    {title && <h2 className="text-lg font-semibold text-brand-900 mb-4">{title}</h2>}
    {children}
  </section>
);

export const Empty = ({ text }: { text: string }) => (
  <p className="text-sm text-gray-500 py-6 text-center">{text}</p>
);

export const Table = ({ head, children }: { head: string[]; children: ReactNode }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-sm text-left">
      <thead>
        <tr className="border-b border-gray-200 text-gray-500">
          {head.map((h) => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  </div>
);
export const Td = ({ children }: { children: ReactNode }) => (
  <td className="py-2 pr-4 border-b border-gray-100 align-middle">{children}</td>
);

export function CertTable({ certs, store }: { certs: Cert[]; store: Store }) {
  if (!certs.length) return <Empty text="No certificates yet." />;
  return (
    <Table head={["Student", "Type", "Title", "Submitted", "Status"]}>
      {certs.map((c) => (
        <tr key={c.id}>
          <Td>{store.students.find((s) => s.id === c.studentId)?.name ?? "—"}</Td>
          <Td>{c.category}</Td><Td>{c.title}</Td><Td>{c.submitted}</Td><Td><Badge status={c.status} /></Td>
        </tr>
      ))}
    </Table>
  );
}

export function Leaderboard({ store, cls }: { store: Store; cls: ClassName }) {
  const month = new Date().toISOString().slice(0, 7);
  const [data, setData] = useState<LB | null>(null);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [newRank, setNewRank] = useState("");
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState(false);

  const load = useCallback(() => {
    store.getLeaderboard(cls).then(setData).catch((e: Error) => setErr(e.message));
  }, [store, cls]);
  // reload when class changes or when certificates change (e.g. after an approval)
  useEffect(load, [load, store.certs]);

  const save = async () => {
    try {
      await store.adjustRank!(editing!, Number(newRank), reason);
      setEditing(null); setNewRank(""); setReason(""); setConfirm(false); setErr(""); load();
    } catch (e) { setErr((e as Error).message); setConfirm(false); }
  };
  const valid = Number(newRank) >= 1 && reason.trim().length >= 3;

  return (
    <Panel title={`${cls} leaderboard – ${month}`}>
      {err && <p role="alert" className="mb-3 text-sm text-red-700">{err}</p>}
      {!data ? <Empty text="Loading…" /> : (
        <>
          {data.top && (
            <p className="mb-4 text-sm bg-brand-50 border border-blue-200 rounded px-3 py-2">
              Student of the Month: <strong>{data.top}</strong>
            </p>
          )}
          {data.rows.length === 0 ? <Empty text="No approved activity this month yet." /> : (
            <Table head={["Rank", "Student", "Roll No.", ...(data.rows[0].count !== undefined ? ["Approved"] : []), "Points", ...(store.adjustRank ? [""] : [])]}>
              {data.rows.map((r) => (
                <tr key={r.id ?? r.roll}>
                  <Td>{r.rank}</Td><Td>{r.name}</Td><Td>{r.roll}</Td>
                  {r.count !== undefined && <Td>{r.count}</Td>}
                  <Td>{r.score}</Td>
                  {store.adjustRank && <Td><button className={btnGhost} onClick={() => setEditing(r.id ?? null)}>Change rank</button></Td>}
                </tr>
              ))}
            </Table>
          )}
          {editing && (
            <div className="mt-4 border border-gray-200 rounded p-3 max-w-md space-y-2">
              <label htmlFor="nr" className="block text-sm">New rank</label>
              <input id="nr" type="number" min={1} className={input} value={newRank} onChange={(e) => setNewRank(e.target.value)} />
              <label htmlFor="rs" className="block text-sm">Reason (recorded in the audit log)</label>
              <input id="rs" className={input} value={reason} onChange={(e) => setReason(e.target.value)} />
              {confirm ? (
                <div role="alertdialog" className="text-sm bg-amber-50 border border-amber-300 rounded p-2">
                  <p className="mb-2">Change this student's rank to {newRank}? This will be logged.</p>
                  <button className={btn} onClick={save}>Confirm</button>{" "}
                  <button className={btnGhost} onClick={() => setConfirm(false)}>Cancel</button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <button className={btn} disabled={!valid} onClick={() => setConfirm(true)}>Save</button>
                  <button className={btnGhost} onClick={() => setEditing(null)}>Cancel</button>
                </div>
              )}
            </div>
          )}
          <p className="text-xs text-gray-500 mt-3">Only approved certificates count towards points.</p>
        </>
      )}
    </Panel>
  );
}
