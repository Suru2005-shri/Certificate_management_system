"""Controlled HOD provisioning. Run once per department by an administrator:
    DATABASE_URL=... python scripts/create_hod.py CS "Dr. Name" hod@college.edu 9876543210
Department codes: CS, AIML, IT, CIVIL. Each department has exactly ONE active HOD.
The HOD then registers/logs in through Keycloak with the SAME verified email; the backend links the account on first login.
HOD can never be created through the student sign-up flow."""
import os
import sys

import psycopg

if len(sys.argv) != 5:
    sys.exit(__doc__)
dept, name, email, phone = sys.argv[1:5]
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    d = c.execute("select id from departments where code = %s", (dept.upper(),)).fetchone()
    if not d:
        sys.exit(f"Unknown department {dept!r}. Use CS, AIML, IT or CIVIL.")
    if c.execute("select 1 from profiles where department_id=%s and role='hod' and active and lower(email)<>lower(%s)",
                 (d[0], email)).fetchone():
        sys.exit(f"{dept.upper()} already has an active HOD. Deactivate that profile first (update profiles set active=false ...).")
    c.execute("insert into profiles (full_name, email, phone, department_id, role) values (%s,%s,%s,%s,'hod') "
              "on conflict (email) do nothing", (name, email, phone, d[0]))
print(f"HOD profile for {dept.upper()} ready for {email}. Ask them to sign in with that verified email.")
