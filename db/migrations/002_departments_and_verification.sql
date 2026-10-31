-- Run ONCE in the Supabase SQL Editor on an existing database (created from the old schema.sql).
-- It is safe to run again: every step checks first. Existing data is kept and becomes the IT department.
-- Deploy the new backend right after this migration (the old backend does not know the new columns).
begin;

-- 1. Departments ------------------------------------------------------------------------------
create table if not exists departments (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  position int not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now()
);
alter table departments enable row level security;
insert into departments (code, name, position) values
  ('CS','Computer Science',1), ('AIML','Artificial Intelligence and Machine Learning',2),
  ('IT','Information Technology',3), ('CIVIL','Civil Engineering',4)
on conflict (code) do nothing;

-- 2. Classes belong to a department (SE/TE/BE in each) ------------------------------------------
alter table classes add column if not exists department_id uuid references departments(id);
update classes set department_id = (select id from departments where code = 'IT') where department_id is null;
alter table classes alter column department_id set not null;
alter table classes drop constraint if exists classes_class_name_key;
create unique index if not exists classes_department_class_uq on classes(department_id, class_name);
insert into classes (department_id, class_name)
  select d.id, c.n from departments d cross join (values ('SE'),('TE'),('BE')) as c(n)
on conflict (department_id, class_name) do nothing;

-- 3. Every profile belongs to a department; one active HOD per department -------------------------
alter table profiles add column if not exists department_id uuid references departments(id);
update profiles p set department_id = coalesce(
    (select c.department_id from classes c where c.id = p.class_id),
    (select id from departments where code = 'IT'))
  where p.department_id is null;
alter table profiles alter column department_id set not null;
create index if not exists profiles_department_id_idx on profiles(department_id);
create unique index if not exists one_active_hod_per_department on profiles(department_id) where role = 'hod' and active;

-- 4. Scoring rules per department (each department's HOD edits only their own) -------------------
alter table scoring_rules add column if not exists department_id uuid references departments(id);
update scoring_rules set department_id = (select id from departments where code = 'IT') where department_id is null;
alter table scoring_rules drop constraint if exists scoring_rules_category_key;
alter table scoring_rules alter column department_id set not null;
create unique index if not exists scoring_rules_department_category_uq on scoring_rules(department_id, category);
insert into scoring_rules (department_id, category, base_points, bonus_rule, active)
  select d.id, r.category, r.base_points, r.bonus_rule, r.active
  from departments d join scoring_rules r on r.department_id = (select id from departments where code = 'IT')
  where d.code <> 'IT'
on conflict (department_id, category) do nothing;

-- 5. The old text department columns are replaced by department_id ------------------------------
alter table profiles drop column if exists department;
alter table classes drop column if exists department;

-- 6. Certificate verification: certificate number + reuse / tampering fingerprints -----------------
alter table certificate_submissions add column if not exists certificate_no text;
alter table certificate_submissions add column if not exists cert_numbers text[] not null default '{}';
alter table certificate_files add column if not exists sha256 text;
alter table certificate_files add column if not exists phash text;
create index if not exists certificate_files_sha256_idx on certificate_files(sha256);
create index if not exists certificate_submissions_cert_numbers_idx on certificate_submissions using gin (cert_numbers);

commit;
