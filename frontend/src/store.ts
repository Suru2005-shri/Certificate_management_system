import { useCallback, useState } from "react";
import { SEED_CERTS, STUDENTS, TEACHERS, certPoints } from "./data";
import type { AuditEntry, Cert, ClassName, Leaderboard, Store, Teacher } from "./types";

/** Demo store: in-memory sample data so every screen can be reviewed without servers. */
export function useDemoStore(): Store {
  const [teachers, setTeachers] = useState<Teacher[]>(TEACHERS);
  const [certs, setCerts] = useState<Cert[]>(SEED_CERTS);
  const [audit, setAudit] = useState<AuditEntry[]>([]);

  const log = useCallback((actor: string, action: string, target: string) => {
    setAudit((a) => [{ at: new Date().toLocaleString(), actor, action, target }, ...a]);
  }, []);
  const demoScore = (f: Record<string, string>) =>
    Math.min(95, 50 + Object.values(f).filter((v) => v.trim()).length * 8);

  return {
    students: STUDENTS, teachers, certs, audit, notifications: [], rules: [], stats: null,

    async submit(student, category, fields, file) {
      const cert: Cert = {
        id: `c${Date.now()}`, studentId: student.id, category,
        title: fields.title || fields.otherType || category, fields, fileName: file.name,
        status: "Pending", score: demoScore(fields), submitted: new Date().toISOString().slice(0, 10),
      };
      setCerts((c) => [cert, ...c]);
      log(student.name, "Certificate submitted", cert.title);
    },
    async resubmit(id, fields) {
      setCerts((cs) => cs.map((c) => (c.id === id ? { ...c, fields, title: fields.title || c.title, status: "Pending", remark: undefined } : c)));
    },
    async review(id, status, remark, actor) {
      setCerts((cs) => cs.map((c) => (c.id === id ? { ...c, status, remark } : c)));
      log(actor, `Certificate ${status.toLowerCase()}`, certs.find((x) => x.id === id)?.title ?? id);
    },
    async addTeacher(t, actor) {
      setTeachers((ts) => [...ts, { id: `t${Date.now()}`, name: t.name, cls: t.cls, active: true }]);
      log(actor, "Teacher added", `${t.name} (${t.cls})`);
      return "DEMO-CODE-1234";
    },
    async setTeacherActive(id, active, actor) {
      setTeachers((ts) => ts.map((x) => (x.id === id ? { ...x, active } : x)));
      log(actor, active ? "Teacher activated" : "Teacher deactivated", teachers.find((x) => x.id === id)?.name ?? id);
    },
    async assignTeacher(id, cls, actor) {
      setTeachers((ts) => ts.map((x) => (x.id === id ? { ...x, cls } : x)));
      log(actor, "Teacher reassigned", `${teachers.find((x) => x.id === id)?.name ?? id} → ${cls}`);
    },
    async updateRule() { /* read-only in demo */ },

    async getLeaderboard(cls) { return demoLeaderboard(certs, cls); },
    async getDetail(id) {
      const c = certs.find((x) => x.id === id);
      return {
        fields: { title: c?.title ?? "", ...(c?.fields ?? {}) },
        files: c ? [{ id: "f1", name: c.fileName, kind: "certificate" }] : [],
        score: c?.score ?? null, label: null, notes: [], signals: [],
      };
    },
    async fileUrl() { return ""; },
    async markNotificationsRead() { /* none in demo */ },
  };
}

function demoLeaderboard(certs: Cert[], cls: ClassName): Leaderboard {
  const month = new Date().toISOString().slice(0, 7);
  const rows = STUDENTS.filter((s) => s.cls === cls).map((s) => {
    const mine = certs.filter((c) => c.studentId === s.id && c.status === "Approved" && c.submitted.startsWith(month));
    return { name: s.name, roll: s.roll, count: mine.length, score: mine.reduce((n, c) => n + certPoints(c), 0), rank: 0 };
  }).sort((a, b) => b.score - a.score || (b.count ?? 0) - (a.count ?? 0));
  rows.forEach((r, i) => { r.rank = i + 1; });
  return { rows, top: rows[0]?.score ? rows[0].name : null };
}
