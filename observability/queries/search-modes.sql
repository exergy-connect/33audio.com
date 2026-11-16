-- Part search by mode over the last 24 hours (Workers Analytics Engine SQL API).
-- Written by functions/api/search.js: blob1 = mode, blob2 = ok|fallback, double1 = took_ms, double2 = result count.
SELECT
  blob1 AS mode,
  blob2 AS outcome,
  SUM(_sample_interval) AS searches,
  quantileWeighted(0.5)(double1, _sample_interval) AS p50_ms,
  quantileWeighted(0.95)(double1, _sample_interval) AS p95_ms,
  SUM(_sample_interval * double2) / SUM(_sample_interval) AS avg_results
FROM caddock_search
WHERE timestamp > NOW() - INTERVAL '1' DAY
GROUP BY mode, outcome
ORDER BY searches DESC
