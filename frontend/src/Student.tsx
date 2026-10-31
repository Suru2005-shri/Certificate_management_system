import { useEffect, useState } from "react";
import { ADVISORS, CATEGORIES, CATEGORY_FIELDS } from "./data";
import { Badge, Card, CertTable, Empty, Leaderboard, Panel, Table, Td, btn, btnGhost, input } from "./Shared";
import type { Category, Cert, Store, Student } from "./types";

const ALLOWED = ["application/pdf", "image/jpeg", "image/png"];
const MAX_BYTES = 5 * 1024 * 1024;

export function StudentPages({ view, student, store, go, advisor }: {
  view: string; student: Student; store: Store; go: (v: string) => void; advisor?: string | null;
}) {
  const [resubmitting, setResubmitting] = useState<Cert | null>(null);
  const [rank, setRank] = useState<number | null>(null);
  const mine = store.certs.filter((c) => c.studentId === student.id);
  const approved = mine.filter((c) => c.status === "Approved");

  useEffect(() => {
    store.getLeaderboard(student.cls)
      .then((lb) => setRank(lb.rows.find((r) => r.roll === student.roll)?.rank ?? null))
      .catch(() => setRank(null));
  }, [store, student, store.certs]);

  if (resubmitting)
    return <UploadForm student={student} store={store} resubmit={resubmitting}
      done={() => { setResubmitting(null); go("certs"); }} />;
  if (view === "upload") return <UploadForm student={student} store={store} done={() => go("certs")} />;
  if (view === "certs")
    return (
      <Panel title="My Certificates">
        {mine.length === 0 ? <Empty text="You have not submitted any certificates." /> : (
          <Table head={["Type", "Title", "Submitted", "Status", "Remark", ""]}>
            {mine.map((c) => (
              <tr key={c.id}>
                <Td>{c.category}</Td><Td>{c.title}</Td><Td>{c.submitted}</Td>
                <Td><Badge status={c.status} /></Td><Td>{c.remark ?? "—"}</Td>
                <Td>{c.status === "Resubmission Required" &&
                  <button className={btnGhost} onClick={() => setResubmitting(c)}>Resubmit</button>}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
    );
  if (view === "leaderboard") return <Leaderboard store={store} cls={student.cls} />;
  if (view === "profile")
    return (
      <Panel title="Profile">
        <dl className="grid grid-cols-2 gap-y-2 text-sm max-w-md">
          <dt className="text-gray-500">Name</dt><dd>{student.name}</dd>
          <dt className="text-gray-500">Roll No.</dt><dd>{student.roll}</dd>
          <dt className="text-gray-500">Class</dt><dd>{student.cls}</dd>
          <dt className="text-gray-500">Class Advisor</dt><dd>{advisor ?? ADVISORS[student.cls]}</dd>
        </dl>
        <h3 className="font-medium mt-6 mb-2">Verified achievements</h3>
        {approved.length ? <CertTable certs={approved} store={store} /> : <Empty text="No verified certificates yet." />}
      </Panel>
    );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <Card title="Total Certificates" value={mine.length} />
        <Card title="Verified" value={approved.length} />
        <Card title="Pending" value={mine.filter((c) => c.status === "Pending" || c.status === "Under Review").length} />
        <Card title="Skills / Areas" value={new Set(approved.map((c) => c.category)).size} />
        <Card title="Monthly Rank" value={rank && approved.length ? `#${rank}` : "—"} />
      </div>
      <UploadForm student={student} store={store} done={() => go("certs")} />
    </div>
  );
}

function UploadForm({ student, store, done, resubmit }: {
  student: Student; store: Store; done: () => void; resubmit?: Cert;
}) {
  const [category, setCategory] = useState<Category>(resubmit?.category ?? "Workshop");
  const [values, setValues] = useState<Record<string, string>>({});
  const [file, setFile] = useState<File | null>(null);
  const [photos, setPhotos] = useState<File[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const fields = CATEGORY_FIELDS[category].filter((f) => !f.showIf || f.showIf(values));

  // Resubmission: load the saved details so the student only corrects what is needed
  useEffect(() => {
    if (resubmit) store.getDetail(resubmit.id).then((d) => setValues(d.fields)).catch((e: Error) => setErrors([e.message]));
  }, [resubmit?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k: string, v: string) => setValues((x) => ({ ...x, [k]: v }));
  const changeCategory = (c: Category) => { setCategory(c); setValues({}); setErrors([]); };

  const checkFile = (f: File, errs: string[], label: string) => {
    if (!ALLOWED.includes(f.type)) errs.push(`${label} must be a PDF, JPG or PNG file.`);
    else if (f.size > MAX_BYTES) errs.push(`${label} must be 5 MB or smaller.`);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs: string[] = [];
    fields.forEach((f) => { if (f.required && !values[f.key]?.trim()) errs.push(`${f.label} is required.`); });
    if (values.start && values.end && values.end < values.start) errs.push("End date cannot be before start date.");
    if (!file && !resubmit) errs.push("Please attach your certificate.");
    if (file) checkFile(file, errs, "Certificate");
    photos.forEach((p) => { if (!p.type.startsWith("image/")) errs.push("Event photos must be JPG or PNG."); else checkFile(p, errs, "Each photo"); });
    setErrors(errs);
    if (errs.length) return;
    setBusy(true);
    try {
      if (resubmit) await store.resubmit(resubmit.id, values, file);
      else await store.submit(student, category, values, file!, photos);
      done();
    } catch (err) {
      setErrors([(err as Error).message]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={resubmit ? "Resubmit Certificate" : "Upload Certificate"}>
      {resubmit?.remark && <p className="mb-4 text-sm bg-amber-50 border border-amber-200 rounded p-3">Teacher's remark: {resubmit.remark}</p>}
      <form onSubmit={submit} className="space-y-4 max-w-2xl" noValidate>
        <div>
          <label htmlFor="cat" className="block text-sm mb-1">Certificate Type</label>
          <select id="cat" className={input} value={category} disabled={!!resubmit} onChange={(e) => changeCategory(e.target.value as Category)}>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>

        {fields.map((f) => (
          <div key={f.key}>
            <label htmlFor={f.key} className="block text-sm mb-1">
              {f.label}{f.required && <span className="text-red-600"> *</span>}
            </label>
            {f.type === "textarea" ? (
              <textarea id={f.key} rows={3} className={input} value={values[f.key] ?? ""} onChange={(e) => set(f.key, e.target.value)} />
            ) : f.type === "select" ? (
              <select id={f.key} className={input} value={values[f.key] ?? ""} onChange={(e) => set(f.key, e.target.value)}>
                <option value="">Select…</option>
                {f.options!.map((o) => <option key={o}>{o}</option>)}
              </select>
            ) : (
              <input id={f.key} type={f.type} className={input} value={values[f.key] ?? ""} onChange={(e) => set(f.key, e.target.value)} />
            )}
          </div>
        ))}

        {category === "Sports" && !resubmit && (
          <div>
            <label htmlFor="photos" className="block text-sm mb-1">Event Photos (JPG/PNG, up to 5)</label>
            <input id="photos" type="file" accept="image/jpeg,image/png" multiple className="text-sm"
              onChange={(e) => setPhotos(Array.from(e.target.files ?? []).slice(0, 5))} />
          </div>
        )}

        <div>
          <label htmlFor="file" className="block text-sm mb-1">
            Certificate (PDF/JPG/PNG, max 5 MB){!resubmit && <span className="text-red-600"> *</span>}
          </label>
          <input id="file" type="file" accept=".pdf,image/jpeg,image/png" className="text-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          {resubmit && <p className="text-xs text-gray-500 mt-1">Leave empty to keep the file you uploaded before.</p>}
        </div>

        {errors.length > 0 && (
          <ul role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3 list-disc pl-6">
            {errors.map((e) => <li key={e}>{e}</li>)}
          </ul>
        )}
        <div className="flex gap-2">
          <button className={btn} type="submit" disabled={busy}>{busy ? "Submitting…" : resubmit ? "Resubmit" : "Submit for verification"}</button>
          {resubmit && <button type="button" className={btnGhost} onClick={done}>Cancel</button>}
        </div>
      </form>
    </Panel>
  );
}
