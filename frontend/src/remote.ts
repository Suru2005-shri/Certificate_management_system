import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type {
  AuditEntry, Category, Cert, ClassName, Detail, Notice, Role, Rule, Stats, Status, Store, Student, Teacher,
} from "./types";

export interface Me {
  id: string; full_name: string; role: Role; roll_no: string | null; class_name: ClassName | null; advisor: string | null;
  department: string; department_name: string;
}

const CAT_LABEL: Record<string, Category> = {
  workshop: "Workshop", internship: "Internship", hackathon: "Hackathon",
  participation: "Participation Certificate", sports: "Sports", other: "Other",
};
const CAT_KEY: Record<Category, string> = {
  Workshop: "workshop", Internship: "internship", Hackathon: "hackathon",
  "Participation Certificate": "participation", Sports: "sports", Other: "other",
};
const STATUS_LABEL: Record<string, Status> = {
  pending: "Pending", under_review: "Under Review", approved: "Approved",
  rejected: "Rejected", resubmission_required: "Resubmission Required",
};
const STATUS_KEY: Record<string, string> = {
  Approved: "approve", Rejected: "reject", "Resubmission Required": "request-resubmission",
};

type Row = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const toCert = (r: Row, fallbackStudent = ""): Cert => ({
  id: r.id, studentId: r.student_id ?? fallbackStudent, category: CAT_LABEL[r.category] ?? "Other", title: r.title,
  fields: {}, fileName: "", status: STATUS_LABEL[r.status] ?? "Pending",
  score: r.verification_score == null ? null : Number(r.verification_score),
  remark: r.teacher_remark ?? undefined, submitted: String(r.created_at ?? r.verified_at ?? "").slice(0, 10),
});

/** API row -> the form's field keys (same keys the backend validates). */
function toFields(r: Row): Record<string, string> {
  const f: Record<string, string> = {
    title: r.title ?? "", duration: r.duration ?? "", start: r.start_date ?? "", end: r.end_date ?? "",
    mode: r.mode ?? "", place: r.place ?? "", prize: r.prize ?? "", level: r.sport_level ?? "", otherType: r.other_type ?? "",
    certificateNo: r.certificate_no ?? "",
  };
  if (r.category === "internship") f.skills = r.learning ?? (r.skills ?? []).join(", ");
  else f.learning = r.learning ?? "";
  return Object.fromEntries(Object.entries(f).filter(([, v]) => v));
}

export function useRemoteStore(me: Me): Store {
  const [students, setStudents] = useState<Student[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [certs, setCerts] = useState<Cert[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [notifications, setNotifications] = useState<Notice[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);

  const refresh = useCallback(async () => {
    const notices = api.get<Row[]>("/notifications").then((rows) =>
      setNotifications(rows.map((n) => ({ id: n.id, title: n.title, message: n.message ?? "", at: String(n.created_at).slice(0, 16).replace("T", " "), read: !!n.read_at }))));

    if (me.role === "student") {
      const [mine] = await Promise.all([api.get<Row[]>("/certificates/my"), notices]);
      setCerts(mine.map((r) => toCert(r, me.id)));
      setStudents([{ id: me.id, name: me.full_name, roll: me.roll_no ?? "", cls: me.class_name ?? "SE" }]);
    } else if (me.role === "teacher") {
      const cls = me.class_name ?? "SE";
      const [pending, approved, studs, dash] = await Promise.all([
        api.get<Row[]>("/teacher/pending"), api.get<Row[]>("/teacher/approved"),
        api.get<Row[]>("/teacher/students"), api.get<Row>("/teacher/dashboard"), notices]);
      setCerts([...pending, ...approved].map((r) => toCert(r)));
      setStudents(studs.map((s) => ({ id: s.id, name: s.full_name, roll: s.roll_no, cls, approvedCount: Number(s.verified_certificates) })));
      setStats({ pending: Number(dash.pending), approved: Number(dash.approved_this_month),
        rejectedOrResubmission: Number(dash.rejected_or_resubmission), participating: Number(dash.participating_students) });
    } else {
      const [studs, cs, ts, rs, logs, sum] = await Promise.all([
        api.get<Row[]>("/hod/students"), api.get<Row[]>("/hod/certificates?limit=200"), api.get<Row[]>("/hod/teachers"),
        api.get<Row[]>("/hod/scoring-rules"), api.get<Row[]>("/hod/audit-logs?limit=200"), api.get<Row>("/hod/summary"), notices]);
      setStudents(studs.map((s) => ({ id: s.id, name: s.full_name, roll: s.roll_no, cls: s.class_name, approvedCount: Number(s.approved_certificates) })));
      setCerts(cs.map((r) => toCert(r)));
      setTeachers(ts.map((t) => ({ id: t.id, name: t.full_name, cls: t.class_name ?? null, active: !!t.active })));
      setRules(rs.map((r) => ({ id: r.id, category: r.category, base: r.base_points, active: r.active })));
      setAudit(logs.map((a) => ({ at: String(a.created_at).slice(0, 16).replace("T", " "), actor: a.actor ?? "—", action: String(a.action).replace(/_/g, " "), target: a.entity_type })));
      setStats({ pending: Number(sum.pending), approved: Number(sum.approved), rejectedOrResubmission: 0, participating: Number(sum.students) });
    }
  }, [me]);

  useEffect(() => { refresh().catch(() => undefined); }, [refresh]);

  const detailPath = (id: string) => (me.role === "student" ? `/certificates/${id}` : `/teacher/submissions/${id}`);

  return {
    students, teachers, certs, audit, notifications, rules, stats,

    async submit(_student, category, fields, file, photos) {
      const fd = new FormData();
      fd.append("category", CAT_KEY[category]);
      fd.append("fields", JSON.stringify(fields));
      fd.append("certificate", file);
      photos.forEach((p) => fd.append("photos", p));
      await api.form("/certificates", fd);
      await refresh();
    },
    async resubmit(id, fields, file) {
      const fd = new FormData();
      fd.append("fields", JSON.stringify(fields));
      if (file) fd.append("certificate", file);
      await api.form(`/certificates/${id}/resubmit`, fd);
      await refresh();
    },
    async review(id, status, remark) {
      await api.post(`/teacher/submissions/${id}/${STATUS_KEY[status]}`, { remark });
      await refresh();
    },
    async addTeacher(t) {
      const r = await api.post<Row>("/hod/teachers", {
        full_name: t.name, email: t.email, phone: t.phone, class_name: t.cls, can_adjust_ranking: t.canAdjust });
      await refresh();
      return r.access_code as string;
    },
    async setTeacherActive(id, active) {
      await api.patch(`/hod/teachers/${id}`, { active });
      await refresh();
    },
    async assignTeacher(id, cls) {
      await api.post("/hod/teacher-assignments", { teacher_id: id, class_name: cls });
      await refresh();
    },
    async updateRule(id, base) {
      await api.patch(`/hod/scoring-rules/${id}`, { base_points: base });
      await refresh();
    },

    async getLeaderboard(cls) {
      const month = new Date().toISOString().slice(0, 7);
      const r = await api.get<Row>(`/leaderboard/${cls}/${month}`);
      return {
        top: r.student_of_the_month ?? null,
        rows: (r.rows as Row[]).map((x) => ({ id: x.id, name: x.full_name, roll: x.roll_no, score: x.score, rank: x.final_rank })),
      };
    },
    adjustRank: me.role === "teacher"
      ? async (rowId, newRank, reason) => { await api.post(`/teacher/leaderboard/${rowId}/adjust`, { new_rank: newRank, reason }); }
      : undefined,

    async getDetail(id): Promise<Detail> {
      const r = await api.get<Row>(detailPath(id));
      return {
        fields: toFields(r),
        files: (r.files as Row[]).map((f) => ({ id: f.id, name: f.file_name, kind: f.file_kind })),
        score: r.verification_score == null ? null : Number(r.verification_score),
        label: r.verification_flags?.label ?? null,
        notes: r.verification_flags?.notes ?? [],
        signals: r.verification_flags?.signals ?? [],
      };
    },
    async fileUrl(certId, fileId) {
      const path = me.role === "student" ? `/certificates/${certId}/files/${fileId}/url` : `/teacher/submissions/${certId}/files/${fileId}/url`;
      return (await api.get<{ url: string }>(path)).url;
    },
    async markNotificationsRead() {
      await api.post("/notifications/read");
      await refresh();
    },
  };
}
