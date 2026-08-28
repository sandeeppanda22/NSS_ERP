# NSS ERP — UI Mockups

Reference HTML files using Tailwind CSS + DaisyUI. These are **static visual targets** for Phase 4 implementation — not functional prototypes.

## Files

| File | Screen | Description |
|------|--------|-------------|
| `01_login.html` | UI-001 Login | Centered card, saffron accent, Sangha Sevi ID field |
| `02_kendra_dashboard.html` | UI-002 Kendra Dashboard | Stats, renewal/attendance cards, governance section, sidebar nav |
| `03_sakha_dashboard.html` | UI-003 Sakha Dashboard | Scoped stats, quick actions, member table |
| `04_admin.html` | Administration | Navigation tiles, user management with RBAC + scope |
| `05_anchalika_dashboard.html` | Anchalika Dashboard | Multi-Sakha overview table, alerts, aggregate stats |
| `06_zilla_dashboard.html` | Zilla Dashboard | District-level Sakha performance, insights cards |
| `07_member_profile.html` | UI-005 Member Profile | Tabbed view: personal, membership, family, attendance |
| `08_family_dashboard.html` | UI-006 Family Dashboard | Family members, head history, Kumari/Kishor youth participation |
| `09_member_search.html` | UI-004 Member Search | Search bar, filter chips, results table with pagination |
| `10_attendance_marking.html` | Attendance Marking | Weekly Sangha Puja P/A/L toggle grid, progress bar, submit |
| `11_governance_dashboard.html` | Governance Dashboard | Statutory bodies, GB composition table, meeting history |
| `12_mahila_mandali_dashboard.html` | Mahila Parichalana Mandali (Kendra) | Central governing body for all branch Mahila Sanghas, Mandali positions, branch performance |
| `13_mahila_sakha_dashboard.html` | Sakha Mahila Sangha | Local branch Mahila members, Kumari youth wing, quick actions, recent activity |

## How to View

Open any file directly in a browser — they load Tailwind and DaisyUI from CDN, no build step needed.

## Design Language

- **Saffron (#DC7831):** NSS brand accent
- **Indigo:** People/Members
- **Green:** Families/Success
- **Amber:** Renewals/Warnings
- **Blue:** Attendance/Info
- **Pink:** Mahila Sangha
- **Purple:** Governance/Transfer
- **Red:** Admin/Critical

## Notes

- These use CDN-loaded Tailwind (for portability). Production will use a compiled Tailwind build.
- Data shown is sample/placeholder — not from a real database.
- Sidebar navigation in Kendra Dashboard shows the full module list.
- All screens are responsive (resize browser to test mobile view).
