import type { Category, Cert, ClassName, Student, Teacher } from "./types";

export const CLASSES: ClassName[] = ["SE", "TE", "BE"];
export const ADVISORS: Record<ClassName, string> = {
  SE: "Prof. Sonali Karthik", TE: "Prof. Swarang Raut", BE: "Prof. Simran Patil",
};
export const CATEGORIES: Category[] = [
  "Workshop", "Internship", "Hackathon", "Participation Certificate", "Sports", "Other",
];

// Transparent points table (HOD-configurable later)
export const POINTS: Record<Category, number> = {
  Workshop: 5, Internship: 15, Hackathon: 10, "Participation Certificate": 3, Sports: 8, Other: 3,
};
const SPORT_BONUS: Record<string, number> = {
  College: 0, Taluka: 1, District: 2, Zonal: 3, State: 5, National: 8,
};

export function certPoints(c: Cert): number {
  let p = POINTS[c.category];
  if (c.category === "Sports") p += SPORT_BONUS[c.fields.level] ?? 0;
  if (c.category === "Hackathon" && c.fields.prize?.trim()) p += 5;
  return p;
}

export interface Field {
  key: string; label: string; type: "text" | "date" | "textarea" | "select";
  options?: string[]; required?: boolean; showIf?: (v: Record<string, string>) => boolean;
}
const offlinePlace = (label: string): Field => ({
  key: "place", label, type: "text", required: true, showIf: (v) => v.mode === "Offline",
});

const BASE_FIELDS: Record<Category, Field[]> = {
  Workshop: [
    { key: "title", label: "Name of Workshop", type: "text", required: true },
    { key: "duration", label: "Duration", type: "text", required: true },
    { key: "start", label: "Start Date", type: "date", required: true },
    { key: "end", label: "End Date", type: "date", required: true },
    { key: "mode", label: "Mode", type: "select", options: ["Online", "Offline"], required: true },
    offlinePlace("Venue / Place"),
    { key: "learning", label: "What did you learn?", type: "textarea", required: true },
  ],
  Internship: [
    { key: "title", label: "Company Name", type: "text", required: true },
    { key: "duration", label: "Duration", type: "text", required: true },
    { key: "start", label: "Start Date", type: "date", required: true },
    { key: "end", label: "End Date", type: "date", required: true },
    { key: "mode", label: "Mode", type: "select", options: ["Remote", "Hybrid", "Offline"], required: true },
    { key: "skills", label: "Skills developed", type: "textarea", required: true },
  ],
  Hackathon: [
    { key: "title", label: "Hackathon Name", type: "text", required: true },
    { key: "mode", label: "Mode", type: "select", options: ["Online", "Offline"], required: true },
    offlinePlace("Place"),
    { key: "prize", label: "Prize Received (if any)", type: "text" },
  ],
  "Participation Certificate": [
    { key: "title", label: "Event Name", type: "text", required: true },
    { key: "duration", label: "Duration", type: "text", required: true },
    { key: "learning", label: "What did you learn?", type: "textarea", required: true },
    { key: "place", label: "Place", type: "text", required: true },
    { key: "mode", label: "Mode", type: "select", options: ["Online", "Offline"], required: true },
  ],
  Sports: [
    { key: "title", label: "Sport Name", type: "text", required: true },
    { key: "place", label: "Place", type: "text", required: true },
    { key: "level", label: "Level", type: "select",
      options: ["College", "Taluka", "District", "Zonal", "State", "National"], required: true },
  ],
  Other: [
    { key: "otherType", label: "Enter Certificate/Activity Type", type: "text", required: true },
    { key: "title", label: "Title", type: "text", required: true },
    { key: "duration", label: "Duration", type: "text" },
    { key: "learning", label: "What did you learn?", type: "textarea" },
  ],
};

export const STUDENTS: Student[] = [
  { id: "s1", name: "Aarav Mehta", roll: "SE-IT-01", cls: "SE" },
  { id: "s2", name: "Diya Nair", roll: "SE-IT-02", cls: "SE" },
  { id: "s3", name: "Rohan Patil", roll: "TE-IT-01", cls: "TE" },
  { id: "s4", name: "Isha Kulkarni", roll: "TE-IT-02", cls: "TE" },
  { id: "s5", name: "Kabir Shah", roll: "BE-IT-01", cls: "BE" },
  { id: "s6", name: "Meera Joshi", roll: "BE-IT-02", cls: "BE" },
];
export const TEACHERS: Teacher[] = [
  { id: "t1", name: "Prof. Sonali Karthik", cls: "SE", active: true },
  { id: "t2", name: "Prof. Swarang Raut", cls: "TE", active: true },
  { id: "t3", name: "Prof. Simran Patil", cls: "BE", active: true },
];

const thisMonth = new Date().toISOString().slice(0, 7);
export const SEED_CERTS: Cert[] = [
  { id: "c1", studentId: "s1", category: "Workshop", title: "React Fundamentals", fields: { mode: "Online", duration: "2 days" },
    fileName: "react.pdf", status: "Approved", score: 88, submitted: `${thisMonth}-02` },
  { id: "c2", studentId: "s2", category: "Hackathon", title: "Smart City Hack", fields: { mode: "Offline", place: "Mumbai", prize: "2nd place" },
    fileName: "hack.pdf", status: "Approved", score: 91, submitted: `${thisMonth}-03` },
  { id: "c3", studentId: "s1", category: "Sports", title: "Football", fields: { place: "Thane", level: "District" },
    fileName: "foot.jpg", status: "Pending", score: 72, submitted: `${thisMonth}-04` },
  { id: "c4", studentId: "s3", category: "Internship", title: "Infosys", fields: { mode: "Remote", skills: "Python, SQL" },
    fileName: "intern.pdf", status: "Approved", score: 95, submitted: `${thisMonth}-01` },
  { id: "c5", studentId: "s4", category: "Participation Certificate", title: "TechFest", fields: { place: "Pune", mode: "Offline" },
    fileName: "tf.png", status: "Pending", score: 55, submitted: `${thisMonth}-04` },
];

/** Every certificate type also asks for the number printed on the certificate (checked against the file by the automated check). */
const certNo: Field = { key: "certificateNo", label: "Certificate number (printed on the certificate, if any)", type: "text" };
export const CATEGORY_FIELDS = Object.fromEntries(
  Object.entries(BASE_FIELDS).map(([k, v]) => [k, [...v, certNo]]),
) as Record<Category, Field[]>;
