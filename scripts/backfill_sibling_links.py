"""
NSS ERP — Backfill missing SIBLING_OF family_link edges.

Context (owner decision, 2026-10-22): the dashboard Family tab's tree view
is built entirely from nss.family_link edges. Siblings were previously only
ever DERIVED from two people sharing a PARENT_OF edge to a common parent.
When a member added a Brother/Sister via the Add-Member modal and had NO
parent yet in their graph, a nss.family_relationship row was created
(relationship_type_code BROTHER/SISTER, is_current = TRUE — this is why
they show in the plain /members list) but NO family_link edge was created,
so the sibling was invisible in the graph/tree view.

api/routers/family.py (add_family_member / create_family_link) now creates
a direct SIBLING_OF family_link edge going forward (database/ddl/04_family/
05_family_link.sql widens chk_family_link_type to allow it — that DDL
change needs a full hard rebuild before this script's INSERTs can succeed,
since the CHECK constraint must already allow 'SIBLING_OF'). This script
is the one-time fix for family_relationship rows that were created BEFORE
that change shipped and are still missing their family_link edge.

What it finds: every current (is_current = TRUE) nss.family_relationship
row with relationship_type_code IN ('BROTHER', 'SISTER') for a person who
has NO current family_link row at all in that family (person_a_pk or
person_b_pk, any link_type) — i.e. genuinely orphaned, not someone whose
sibling relationship already works via a shared-parent PARENT_OF path
(that case has a link already, so EXISTS excludes them; and even if it
didn't, insert_family_link_edge()'s persons_share_parent() check would
no-op the insert rather than create a redundant edge).

Anchor person: relationship_type_code on family_relationship is relative
to whichever person was the dashboard "viewer" at the time the member was
added (api/routers/family.py / frontend's viewerPersonPk) — that value is
NOT stored, so it cannot be reconstructed exactly. This script anchors
instead to the family's CURRENT head (nss.family_head_history,
effective_to IS NULL) as the most stable, always-present reference point
for "who is this person a sibling of" when the original viewer is unknown.
This is a deliberate, documented approximation — verify it is correct for
each family before running in a sensitive production dataset; for the
owner's two known orphaned rows this is confirmed correct (the orphaned
siblings are siblings of the family head).

Uses the SAME insert_family_link_edge() helper api/routers/family.py's
live endpoints call — not a second parallel implementation of the INSERT
(CLAUDE.md "Shared code — no duplicates"). That helper already no-ops
(returns None, does not raise) if persons_share_parent() finds an existing
shared-parent path, or if an identical edge already exists — so this
script is safe to re-run (idempotent): a second run finds nothing left to
backfill, since every row it would have touched now has a family_link.

Does NOT run automatically and does NOT touch the DB during code review —
only run this by hand, and only AFTER:
  1. The database/ddl/04_family/05_family_link.sql change has gone through
     a full hard rebuild (chk_family_link_type must already permit
     'SIBLING_OF' — this script's INSERTs will fail with a CHECK
     violation otherwise).
  2. api/routers/family.py (insert_family_link_edge et al.) is deployed
     (this script imports it).

Usage:
    python3 scripts/backfill_sibling_links.py            # apply
    python3 scripts/backfill_sibling_links.py --dry-run   # report only

Authority: owner decision, 2026-10-22 (Option B — real SIBLING_OF edge
type; this script is the live-data half of that change, the DDL/BFS/
frontend halves are in the same commit).
"""

import argparse
import sys
from datetime import date
from pathlib import Path

# Ensure the project root is on sys.path so `api.*` imports resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.database import get_write_pool  # noqa: E402
from api.routers.family import insert_family_link_edge  # noqa: E402

# Every current BROTHER/SISTER family_relationship row with NO current
# family_link row at all for that person in that family, paired with the
# family's current head (nss.family_head_history, effective_to IS NULL).
_ORPHANED_SIBLINGS_SQL = """
    SELECT fr.family_relationship_pk,
           fr.family_group_pk,
           fr.person_pk      AS sibling_person_pk,
           fhh.person_pk     AS head_person_pk,
           md.value_code     AS relationship_type_code
    FROM   nss.family_relationship fr
    JOIN   nss.master_data md
           ON md.master_data_pk = fr.relationship_type_master_data_pk
    JOIN   nss.master_category mc
           ON mc.master_category_pk = md.master_category_pk
          AND mc.category_code = 'RELATIONSHIP_TYPE'
    JOIN   nss.family_head_history fhh
           ON fhh.family_group_pk = fr.family_group_pk
          AND fhh.effective_to IS NULL
    WHERE  fr.is_current = TRUE
      AND  md.value_code IN ('BROTHER', 'SISTER')
      AND  fr.person_pk <> fhh.person_pk
      AND  NOT EXISTS (
               SELECT 1 FROM nss.family_link fl
               WHERE  fl.family_group_pk = fr.family_group_pk
                 AND  fl.is_current = TRUE
                 AND  (fl.person_a_pk = fr.person_pk OR fl.person_b_pk = fr.person_pk)
           )
    ORDER BY fr.family_group_pk, fr.person_pk
"""


def main():
    parser = argparse.ArgumentParser(
        description="Backfill missing SIBLING_OF family_link edges for "
                     "orphaned BROTHER/SISTER family_relationship rows."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be inserted, without writing anything.",
    )
    args = parser.parse_args()

    pool = get_write_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(_ORPHANED_SIBLINGS_SQL)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        if not rows:
            print("No orphaned BROTHER/SISTER rows found. Nothing to do.")
            conn.rollback()
            return

        print(f"Found {len(rows)} orphaned BROTHER/SISTER row(s):")
        for r in rows:
            print(
                f"  family {r['family_group_pk']}: "
                f"sibling {r['sibling_person_pk']} "
                f"({r['relationship_type_code']}) <-> head {r['head_person_pk']}"
            )

        if args.dry_run:
            print("\n--dry-run: no changes made.")
            conn.rollback()
            return

        today = date.today()
        created = 0
        skipped = 0
        with conn.cursor() as cur:
            for r in rows:
                fl_pk = insert_family_link_edge(
                    cur,
                    family_group_pk=str(r["family_group_pk"]),
                    person_a_pk=str(r["head_person_pk"]),
                    person_b_pk=str(r["sibling_person_pk"]),
                    link_type="SIBLING_OF",
                    effective_from=today,
                    # No authenticated actor in a standalone script —
                    # same NULL-actor convention get_write_connection()
                    # uses for unauthenticated writes.
                    actor_pk=None,
                    actor_user_account_pk=None,
                )
                if fl_pk is None:
                    skipped += 1
                    print(f"  skipped (already linked/redundant): {r['sibling_person_pk']}")
                else:
                    created += 1
                    print(f"  created family_link {fl_pk} for {r['sibling_person_pk']}")

        conn.commit()
        print(f"\nDone. Created {created}, skipped {skipped} (already covered).")

    except Exception as e:
        conn.rollback()
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        pool.putconn(conn)


if __name__ == "__main__":
    main()
