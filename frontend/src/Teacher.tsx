import { useEffect, useState } from "react";
import { Badge, Card, CertTable, Empty, Leaderboard, Panel, Table, Td, btn, btnGhost, input } from "./Shared";
import type { Cert, Detail, Store, Teacher } from "./types";

const confidence = (n: number | null) =>
  n === null ? "Unable to read" : n >= 80 ? "Likely valid" : n >= 60 ? "Needs review" : "Low confidence";

export function TeacherPages({ view, teacher, store, go }: {
  view: string; teacher: Teacher; store: Store; go: (v: string) => void;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const cls = teacher.cls ?? "SE";
  const classStudents = store.students.filter((s) => s.cls === cls);
  const ids = new Set(classStudents.map((s) => s.id));
  const classCerts = store.certs.filter((c) => ids.has(c.studentId)); // scoped to assigned class only
  const pending = classCerts.filter((c) => c.status === "Pending" || c.status === "Under Review");
  const open = classCerts.find((c) => c.id === openId);
  const approved = classCerts.filter((c) => c.status === "Approved");

  if (open) return <Review cert={open} teacher={teacher} store={store} close={() => { setOpenId(null); go("pending"); }} />;

  if (view === "pending")
    return (
      <Panel title="Pending Certificates">
        {pending.length === 0 ? <Empty text="No pending certificates." /> : (
          <Table head={["Student", "Roll No.", "Type", "Submitted", "Check", ""]}>
            {pending.map((c) => {
              const s = classStudents.find((x) => x.id === c.studentId);
              return (
                <tr key={c.id}>
                  <Td>{s?.name ?? "—"}</Td><Td>{s?.roll ?? "—"}</Td><Td>{c.category}</Td><Td>{c.submitted}</Td>
                  <Td>{c.score === null ? "" : `${c.score}% · `}{confidence(c.score)}</Td>
                  <Td><button className={btnGhost} onClick={() => setOpenId(c.id)}>Review</button></Td>
                </tr>
              );
            })}
          </Table>
        )}
      </Panel>
    );
  if (view === "approved")
    return <Panel title="Approved Certificates"><CertTable certs={approved} store={store} /></Panel>;
  if (view === "students")
    return (
      <Panel title={`Students – ${cls}`}>
        <Table head={["Name", "Roll No.", "Verified certificates"]}>
          {classStudents.map((s) => (
            <tr key={s.id}><Td>{s.name}</Td><Td>{s.roll}</Td>
              <Td>{s.approvedCount ?? classCerts.filter((c) => c.studentId === s.id && c.status === "Approved").length}</Td></tr>
          ))}
        </Table>
      </Panel>
    );
  if (view === "leaderboard") return <Leaderboard store={store} cls={cls} />;

  const st = store.stats;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card title="Pending Submissions" value={st?.pending ?? pending.length} />
        <Card title="Approved" value={st?.approved ?? approved.length} />
        <Card title="Rejected / Resubmission" value={st?.rejectedOrResubmission ??
          classCerts.filter((c) => c.status === "Rejected" || c.status === "Resubmission Required").length} />
        <Card title="Students" value={st?.participating ?? classStudents.length} />
      </div>
      <Panel title="Recent submissions"><CertTable certs={classCerts.slice(0, 6)} store={store} /></Panel>
    </div>
  );
}

function Review({ cert, teacher, store, close }: { cert: Cert; teacher: Teacher; store: Store; close: () => void }) {
  const [remark, setRemark] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<null | "Rejected" | "Resubmission Required">(null);
  const student = store.students.find((s) => s.id === cert.studentId);

  useEffect(() => {
    store.getDetail(cert.id).then(setDetail).catch((e: Error) => setErr(e.message));
  }, [cert.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const decide = async (s: "Approved" | "Rejected" | "Resubmission Required") => {
    setBusy(true); setErr("");
    try { await store.review(cert.id, s, remark, teacher.name); close(); }
    catch (e) { setErr((e as Error).message); setConfirm(null); }
    finally { setBusy(false); }
  };
  const view = async (fileId: string) => {
    try {
      const url = await store.fileUrl(cert.id, fileId);
      if (url) window.open(url, "_blank", "noopener,noreferrer");
      else setErr("File preview is not available in demo mode.");
    } catch (e) { setErr((e as Error).message); }
  };

  const score = detail ? detail.score : cert.score;
  return (
    <Panel title="Review Certificate">
      <dl className="grid grid-cols-2 gap-y-2 text-sm max-w-xl">
        <dt className="text-gray-500">Student</dt><dd>{student ? `${student.name} (${student.roll})` : "—"}</dd>
        <dt className="text-gray-500">Type</dt><dd>{cert.category}</dd>
        {detail && Object.entries(detail.fields).map(([k, v]) => (
          <div key={k} className="contents"><dt className="text-gray-500 capitalize">{k}</dt><dd>{v}</dd></div>
        ))}
        <dt className="text-gray-500">Files</dt>
        <dd className="space-x-2">
          {detail?.files.map((f) => (
            <button key={f.id} className="text-brand-600 underline" onClick={() => view(f.id)}>
              {f.kind === "event_photo" ? "Photo" : "Certificate"}: {f.name}
            </button>
          )) ?? "Loading…"}
        </dd>
        <dt className="text-gray-500">Status</dt><dd><Badge status={cert.status} /></dd>
        <dt className="text-gray-500">Automated check</dt>
        <dd>
          {score === null ? "" : `${score}% – `}{detail?.label ?? confidence(score)}{" "}
          <span className="text-gray-500">(assistance only – you decide)</span>
          {detail?.notes.map((n) => <span key={n} className="block text-xs text-amber-800">⚠ {n}</span>)}
          {detail?.signals.map((s) => (
            <span key={s.code + s.text} className={`block text-xs ${
              s.level === "alert" ? "text-red-700 font-medium" : s.level === "warn" ? "text-amber-800"
              : s.level === "ok" ? "text-green-700" : "text-gray-600"}`}>
              {s.level === "alert" ? "⛔" : s.level === "warn" ? "⚠" : s.level === "ok" ? "✓" : "ℹ"} {s.text}
            </span>
          ))}
        </dd>
      </dl>

      <label htmlFor="remark" className="block text-sm mt-5 mb-1">Remark</label>
      <textarea id="remark" rows={3} className={`${input} max-w-xl`} value={remark} onChange={(e) => setRemark(e.target.value)} />
      {err && <p role="alert" className="mt-3 text-sm text-red-700">{err}</p>}

      {confirm ? (
        <div role="alertdialog" className="mt-4 border border-amber-300 bg-amber-50 rounded p-3 max-w-xl text-sm">
          <p className="mb-3">
            {confirm === "Rejected" ? "Reject" : "Request resubmission of"} this certificate? The student will be notified.
          </p>
          <div className="flex gap-2">
            <button className={btn} disabled={!remark.trim() || busy} onClick={() => decide(confirm)}>Confirm</button>
            <button className={btnGhost} onClick={() => setConfirm(null)}>Cancel</button>
          </div>
          {!remark.trim() && <p className="text-xs mt-2 text-gray-600">A remark is required.</p>}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 mt-4">
          <button className={btn} disabled={busy} onClick={() => decide("Approved")}>Approve</button>
          <button className={btnGhost} onClick={() => setConfirm("Resubmission Required")}>Request resubmission</button>
          <button className={btnGhost} onClick={() => setConfirm("Rejected")}>Reject</button>
          <button className={btnGhost} onClick={close}>Back</button>
        </div>
      )}
    </Panel>
  );
}
