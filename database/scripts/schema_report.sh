# Sourced by 02_build.sh and render_build.sh (not run on its own): the build summary's table report.
#
#   schema_snapshot_to <file>          takes database/scripts/schema_snapshot.sql with the build's own psql connection (${PSQL})
#   schema_report <before> <after>     prints how many tables were created, were already present (DDL skipped) and were altered
#
# "Altered" = the table existed before AND its number of columns, constraints, indexes or triggers changed (what the idempotent patches do:
# ADD COLUMN, ADD CONSTRAINT, CREATE INDEX, CREATE TRIGGER). A patch that found everything already in place changes nothing and is not counted.
# The PowerShell twin is in 02_build.ps1 (Get-SchemaSnapshot / Write-SchemaReport); keep them operationally identical.

SCHEMA_SNAPSHOT_SQL="${SCHEMA_SNAPSHOT_SQL:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/schema_snapshot.sql}"

schema_snapshot_to() {
    # A snapshot that cannot be taken must never fail the build: the report is information only.
    ${PSQL} -qAtX -F '|' -f "${SCHEMA_SNAPSHOT_SQL}" > "$1" 2>/dev/null || : > "$1"
}

schema_report() {
    local before="$1" after="$2" limit="${3:-40}"
    awk -F'|' -v limit="${limit}" '
        function plural(n, w) { return (n > 0 ? "+" : "") n " " w (n == 1 || n == -1 ? "" : "s") }
        FNR == NR { bc[$1] = $2; bk[$1] = $3; bi[$1] = $4; bt[$1] = $5; had[$1] = 1; nb++; next }
        {
            na++
            if (!($1 in had)) { created[++nc] = $1; next }
            dc = $2 - bc[$1]; dk = $3 - bk[$1]; di = $4 - bi[$1]; dt = $5 - bt[$1]
            if (dc || dk || di || dt) {
                d = ""
                if (dc) d = d (d ? ", " : "") plural(dc, "column")
                if (dk) d = d (d ? ", " : "") plural(dk, "constraint")
                if (di) d = d (d ? ", " : "") plural(di, "index") ; if (di) sub(/indexs/, "indexes", d)
                if (dt) d = d (d ? ", " : "") plural(dt, "trigger")
                altered[++nl] = $1 "  (" d ")"
            }
        }
        END {
            printf "  Tables in schema nss: %d (before this run: %d)\n", na, nb
            printf "  Tables created now:   %d\n", nc
            for (i = 1; i <= nc && i <= limit; i++) printf "      + %s\n", created[i]
            if (nc > limit) printf "      ... and %d more\n", nc - limit
            printf "  Tables already there: %d  (DDL skipped, data preserved)\n", nb
            printf "  Tables altered:       %d  (columns / constraints / indexes / triggers added by the patches)\n", nl
            for (i = 1; i <= nl && i <= limit; i++) printf "      ~ %s\n", altered[i]
            if (nl > limit) printf "      ... and %d more\n", nl - limit
        }
    ' "${before}" "${after}"
}
