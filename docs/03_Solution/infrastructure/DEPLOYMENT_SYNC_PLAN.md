# NSS ERP — Deployment and Repository Sync Plan

**Document Type:** Solution Architecture — Infrastructure
**Version:** 1.0
**Date:** 2026-08-16
**Status:** Approved
**Branch:** feature/ref-documentation

---

## Repository Structure

| Remote | URL | Purpose |
|--------|-----|---------|
| `personal` | github.com/sandeeppanda22/NSS_ERP | Daily development, all branches |
| `org` | github.com/NilachalaSaraswataSangha/NSS_ERP | Production deployment source |

---

## Branch Strategy

| Branch | Lives On | Purpose |
|--------|----------|---------|
| `feature/*` | personal only | Active development |
| `develop` | personal only | Integration branch, all features merge here |
| `main` | personal + org | Production-ready code, deployment source |

---

## Daily Workflow

```
Developer codes locally
      |
      v
git push personal feature/xyz       (or develop)
      |
      v
No sync to org — org only receives stable releases
```

---

## Release Workflow

```
Step 1: Merge develop into main (locally)
        git checkout main
        git merge develop

Step 2: Tag the release
        git tag v0.X.0

Step 3: Push to personal
        git push personal main --tags

Step 4: Push to org (triggers deployment)
        git push org main --tags

Step 5: Render.com auto-deploys from org/main
```

---

## Sync Scenarios

| Scenario | Command |
|----------|---------|
| Daily dev push | `git push personal develop` |
| Feature branch push | `git push personal feature/xyz` |
| Release to production | `git push org main --tags` |
| Sync org to match personal main | `git push org main` |
| Check if org is behind | `git fetch org && git log org/main..main --oneline` |
| Hotfix on main | Branch from main, fix, merge, push both personal + org |

---

## What the Org Repo Contains

```
NilachalaSaraswataSangha/NSS_ERP
  main branch only (clean, tagged releases)
  No feature branches
  No develop branch
  Tagged: v0.6.0, v0.7.0, etc.
```

The org repo stays clean — only production-ready, tagged releases.

---

## Org Repo Protection Rules (Recommended)

| Rule | Setting |
|------|---------|
| Default branch | main |
| Force pushes | Disabled |
| Branch deletion | Disabled |
| Other branches | None — org only receives main |

---

## Flow Diagram

```
LOCAL MACHINE
    |
    +-- feature/* ---push---> personal/feature/*
    |       | merge
    +-- develop ----push---> personal/develop
    |       | merge (on release)
    +-- main -------push---> personal/main
                    |
                    +--push---> org/main ---> Render.com deploys
```

---

## One-Time Setup Commands

```bash
# Add org remote (run once)
git remote add org https://github.com/NilachalaSaraswataSangha/NSS_ERP.git

# Verify remotes
git remote -v
```

---

## Release Checklist

1. All features merged to develop
2. Tests passing on develop
3. `git checkout main && git merge develop`
4. Update version in relevant files
5. `git tag vX.Y.Z`
6. `git push personal main --tags`
7. `git push org main --tags`
8. Verify Render.com deployment
9. Create release notes in `docs/05_Releases/`

---

# End of Document
