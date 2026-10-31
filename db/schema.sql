-- Supabase PostgreSQL: application data ONLY.
-- Auth = Keycloak, files = MinIO, logic/authorization = FastAPI (not Supabase Auth/Storage/RLS-by-JWT).
create extension if not exists "pgcrypto";

create type user_role as enum ('student', 'teacher', 'hod');
create type cert_category as enum ('workshop','internship','hackathon','participation','sports','other');
create type cert_status as enum ('pending','under_review','approved','rejected','resubmission_required');

create table departments (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,                     -- CS, AIML, IT, CIVIL
  name text not null,
  position int not null default 0,               -- display order
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table classes (
  id uuid primary key default gen_random_uuid(),
  department_id uuid not null references departments(id),
  class_name text not null check (class_name in ('SE','TE','BE')),
  advisor_id uuid,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (department_id, class_name)
);

create table profiles (
  id uuid primary key default gen_random_uuid(),
  auth_user_id text unique,                     -- Keycloak subject (null until first login)
  full_name text not null,
  email text not null unique,
  phone text,
  roll_no text unique,
  class_id uuid references classes(id),
  department_id uuid not null references departments(id),
  role user_role not null default 'student',
  active boolean not null default true,
  access_code_hash text,                         -- teachers: single-use code issued by HOD
  access_code_expires timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table classes add constraint classes_advisor_fk foreign key (advisor_id) references profiles(id);
-- One active HOD per department
create unique index one_active_hod_per_department on profiles(department_id) where role = 'hod' and active;

create table teacher_assignments (
  id uuid primary key default gen_random_uuid(),
  teacher_id uuid not null references profiles(id),
  class_id uuid not null references classes(id),
  assigned_by uuid references profiles(id),
  can_adjust_ranking boolean not null default false,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table certificate_submissions (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references profiles(id),
  category cert_category not null,
  title text not null,
  start_date date, end_date date,
  duration text, mode text, place text, learning text,
  certificate_no text,                           -- number printed on the certificate, as typed by the student
  cert_numbers text[] not null default '{}',     -- normalized numbers (typed + read by OCR) used to detect reuse
  status cert_status not null default 'pending',
  verification_score numeric(5,2), verification_flags jsonb,
  teacher_remark text,
  verified_by uuid references profiles(id), verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_date is null or start_date is null or end_date >= start_date)
);

create table certificate_details (
  submission_id uuid primary key references certificate_submissions(id) on delete cascade,
  company_name text, prize text, sport_level text check (sport_level in ('College','Taluka','District','Zonal','State','National')),
  skills text[], event_name text, other_type text
);

create table certificate_files (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references certificate_submissions(id) on delete cascade,
  storage_path text not null,                    -- MinIO object key
  file_name text not null, mime_type text not null, size bigint not null,
  file_kind text not null check (file_kind in ('certificate','event_photo')),
  sha256 text,                                   -- exact-file fingerprint (reuse detection)
  phash text,                                    -- perceptual hash of the certificate image (near-duplicate detection)
  created_at timestamptz not null default now()
);

create table student_skills (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references profiles(id),
  skill_name text not null,
  source_submission_id uuid references certificate_submissions(id) on delete cascade,
  created_at timestamptz not null default now()
);

create table scoring_rules (
  id uuid primary key default gen_random_uuid(),
  department_id uuid not null references departments(id),
  category cert_category not null,
  base_points int not null,
  bonus_rule jsonb,
  active boolean not null default true,
  updated_by uuid references profiles(id),
  updated_at timestamptz not null default now(),
  unique (department_id, category)
);

create table leaderboard_monthly (
  id uuid primary key default gen_random_uuid(),
  class_id uuid not null references classes(id),
  month date not null,                           -- first day of month
  student_id uuid not null references profiles(id),
  score int not null default 0,
  rank int, adjusted_rank int,
  adjusted_by uuid references profiles(id), adjustment_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (class_id, month, student_id)
);

create table notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id),
  type text not null, title text not null, message text,
  read_at timestamptz, created_at timestamptz not null default now()
);

create table audit_logs (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid references profiles(id),
  action text not null, entity_type text not null, entity_id uuid,
  metadata jsonb, created_at timestamptz not null default now()
);

-- Indexes on FKs and filter/sort columns
create index on profiles(class_id);
create index on profiles(department_id);
create index on profiles(role);
create index on teacher_assignments(teacher_id);
create index on teacher_assignments(class_id);
create index on certificate_submissions(student_id);
create index on certificate_submissions(status, created_at desc);
create index on certificate_submissions(category);
create index on certificate_files(submission_id);
create index on certificate_files(sha256);
create index on certificate_submissions using gin (cert_numbers);
create index on student_skills(student_id);
create index on leaderboard_monthly(class_id, month, score desc);
create index on notifications(user_id, read_at);
create index on audit_logs(actor_id, created_at desc);
create index on audit_logs(entity_type, entity_id);

-- Defence in depth: the app connects as a least-privilege role and the database
-- is not exposed to browsers (no anon/authenticated access).
alter table profiles enable row level security;
alter table certificate_submissions enable row level security;
alter table certificate_files enable row level security;
alter table audit_logs enable row level security;
alter table departments enable row level security;
-- (No policies for anon/authenticated => browser access via Supabase API is denied.
--  FastAPI uses a dedicated role that is granted access below.)

-- Seed: four departments, SE/TE/BE in each, and the same starting points for every department
insert into departments (code, name, position) values
 ('CS','Computer Science',1), ('AIML','Artificial Intelligence and Machine Learning',2),
 ('IT','Information Technology',3), ('CIVIL','Civil Engineering',4);
insert into classes (department_id, class_name)
 select d.id, c.n from departments d cross join (values ('SE'),('TE'),('BE')) as c(n);
insert into scoring_rules (department_id, category, base_points)
 select d.id, r.category::cert_category, r.points from departments d cross join
 (values ('workshop',5),('internship',15),('hackathon',10),('participation',3),('sports',8),('other',3)) as r(category, points);
