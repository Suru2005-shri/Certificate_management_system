export type ClassName = "SE" | "TE" | "BE";
export type Role = "student" | "teacher" | "hod";
export interface Session { role: Role; id: string }
export type Category =
  | "Workshop" | "Internship" | "Hackathon" | "Participation Certificate" | "Sports" | "Other";
export type Status = "Pending" | "Under Review" | "Approved" | "Rejected" | "Resubmission Required";

export interface Student { id: string; name: string; roll: string; cls: ClassName; approvedCount?: number }
export interface Teacher { id: string; name: string; cls: ClassName | null; active: boolean }
export interface Cert {
  id: string; studentId: string; category: Category; title: string;
  fields: Record<string, string>; fileName: string; status: Status;
  score: number | null; remark?: string; submitted: string; // ISO date
}
export interface AuditEntry { at: string; actor: string; action: string; target: string }
export interface Notice { id: string; title: string; message: string; at: string; read: boolean }
export interface Rule { id: string; category: string; base: number; active: boolean }
export interface Stats { pending: number; approved: number; rejectedOrResubmission: number; participating: number }

export interface Detail {
  fields: Record<string, string>;
  files: { id: string; name: string; kind: string }[];
  score: number | null; label: string | null; notes: string[];
  signals: Signal[];
}
export interface Signal { level: "ok" | "info" | "warn" | "alert"; code: string; text: string }
export interface LbRow { id?: string; name: string; roll: string; count?: number; score: number; rank: number }
export interface Leaderboard { rows: LbRow[]; top: string | null }

export interface NewTeacher { name: string; email: string; phone: string; cls: ClassName; canAdjust: boolean }

/** Everything the screens need. Demo mode and API mode both implement this. */
export interface Store {
  students: Student[]; teachers: Teacher[]; certs: Cert[]; audit: AuditEntry[];
  notifications: Notice[]; rules: Rule[]; stats: Stats | null;
  submit(student: Student, category: Category, fields: Record<string, string>, file: File, photos: File[]): Promise<void>;
  resubmit(id: string, fields: Record<string, string>, file: File | null): Promise<void>;
  review(id: string, status: "Approved" | "Rejected" | "Resubmission Required", remark: string, actor: string): Promise<void>;
  addTeacher(t: NewTeacher, actor: string): Promise<string | null>;   // returns one-time access code in API mode
  setTeacherActive(id: string, active: boolean, actor: string): Promise<void>;
  assignTeacher(id: string, cls: ClassName, actor: string): Promise<void>;
  updateRule(id: string, base: number): Promise<void>;
  getLeaderboard(cls: ClassName): Promise<Leaderboard>;
  adjustRank?: (rowId: string, newRank: number, reason: string) => Promise<void>;
  getDetail(id: string): Promise<Detail>;
  fileUrl(certId: string, fileId: string): Promise<string>;
  markNotificationsRead(): Promise<void>;
}
