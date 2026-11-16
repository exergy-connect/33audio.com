-- Academy lab API traffic per hour, path, and status (Workers Analytics Engine SQL API).
-- Written by academy/worker/index.js: blob1 = path, blob2 = status, blob3 = colo, blob4 = ok|limited, double1 = duration ms.
SELECT
  toStartOfInterval(timestamp, INTERVAL '1' HOUR) AS hour,
  blob1 AS path,
  blob2 AS status,
  SUM(_sample_interval) AS requests,
  SUM(IF(blob4 = 'limited', _sample_interval, 0)) AS rate_limited
FROM academy_lab
WHERE timestamp > NOW() - INTERVAL '1' DAY
GROUP BY hour, path, status
ORDER BY hour, requests DESC
