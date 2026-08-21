SELECT email, created_at, source
FROM (
  SELECT email, created_at, source,
         ROW_NUMBER() OVER (
           PARTITION BY email ORDER BY created_at DESC, id DESC
         ) AS rn
  FROM signups
)
WHERE rn = 1
ORDER BY email
