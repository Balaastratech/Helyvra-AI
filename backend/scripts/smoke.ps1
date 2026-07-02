# Total Recall API smoke test (Phase 2).
#
# Reproduces the demo contrast end-to-end against a running server:
#   1. start the API in another terminal:
#        cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
#   2. run this script:
#        .\scripts\smoke.ps1
#
# Each Cognee call is slow (~3-7s); seed/ingest cognify takes longer. Be patient.

$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8000"

function Show($label, $obj) {
    Write-Host "`n=== $label ===" -ForegroundColor Cyan
    $obj | ConvertTo-Json -Depth 6
}

# 1. Health
Show "GET /health" (Invoke-RestMethod "$base/health")

# 2. Seed baseline (holds back the contradictions)
Show "POST /seed" (Invoke-RestMethod "$base/seed" -Method Post `
    -ContentType "application/json" -Body '{"patient_id":"P001"}')

# 3. Ask BEFORE the heal — both may say allergic (that's fine).
Show "POST /ask naive (pre-heal)" (Invoke-RestMethod "$base/ask" -Method Post `
    -ContentType "application/json" `
    -Body '{"patient_id":"P001","question":"Is the patient allergic to penicillin?","mode":"naive"}')

# 4. Ingest the held-back clear-event (the live heal).
Show "POST /ingest (allergy cleared)" (Invoke-RestMethod "$base/ingest" -Method Post `
    -ContentType "application/json" `
    -Body '{"patient_id":"P001","text":"On 2026-03-02, patient P001 penicillin allergy was cleared after a negative re-test by Dr. Lee.","structured":{"subject":"allergy","predicate":"cleared","value":"penicillin","date":"2026-03-02","source":"Dr. Lee"}}')

# 5. Ingest the med switch.
Show "POST /ingest (med switch)" (Invoke-RestMethod "$base/ingest" -Method Post `
    -ContentType "application/json" `
    -Body '{"patient_id":"P001","text":"On 2026-04-20, patient P001 stopped lisinopril and switched to amlodipine 5mg.","structured":{"subject":"medication","predicate":"switched","value":"amlodipine 5mg","date":"2026-04-20","source":"Dr. Lee"}}')

# 6. The contrast: naive=Yes (stale), total_recall=No (healed).
Show "POST /ask naive (post-heal)" (Invoke-RestMethod "$base/ask" -Method Post `
    -ContentType "application/json" `
    -Body '{"patient_id":"P001","question":"Is the patient allergic to penicillin?","mode":"naive"}')
Show "POST /ask total_recall (post-heal)" (Invoke-RestMethod "$base/ask" -Method Post `
    -ContentType "application/json" `
    -Body '{"patient_id":"P001","question":"Is the patient allergic to penicillin?","mode":"total_recall"}')

# 7. Graph snapshots: allergy active in Feb, superseded now.
Show "GET /graph as_of=2026-02-15" (Invoke-RestMethod "$base/graph?patient_id=P001&as_of=2026-02-15")
Show "GET /graph as_of=2026-06-29" (Invoke-RestMethod "$base/graph?patient_id=P001&as_of=2026-06-29")

# 8. Raw Cognee graph (depth tab).
$cg = Invoke-RestMethod "$base/graph/cognee?patient_id=P001"
Write-Host "`n=== GET /graph/cognee ===" -ForegroundColor Cyan
Write-Host ("nodes={0} edges={1}" -f $cg.nodes.Count, $cg.edges.Count)

# 9. Provenance: pick the superseded allergy node from the graph, then /why.
$g = Invoke-RestMethod "$base/graph?patient_id=P001&as_of=2026-06-29"
$orig = $g.nodes | Where-Object { $_.subject -eq "allergy" -and $_.status -eq "superseded" } | Select-Object -First 1
if ($orig) {
    Show "GET /why (superseded allergy)" (Invoke-RestMethod "$base/why?fact_id=$($orig.id)")
}

# 10. Forget (entered in error): retract the diabetes diagnosis -> vanishes.
$diabetes = $g.nodes | Where-Object { $_.subject -eq "diagnosis" } | Select-Object -First 1
if ($diabetes) {
    Show "POST /forget (diabetes entered in error)" (Invoke-RestMethod "$base/forget" -Method Post `
        -ContentType "application/json" `
        -Body (@{ patient_id = "P001"; fact_id = $diabetes.id; reason = "entered in error - wrong patient" } | ConvertTo-Json))
    $after = Invoke-RestMethod "$base/graph?patient_id=P001&as_of=2026-06-29"
    Write-Host ("after forget: diabetes present = {0}" -f (($after.nodes | Where-Object { $_.id -eq $diabetes.id }).Count -gt 0))
}

Write-Host "`nSmoke test complete." -ForegroundColor Green
