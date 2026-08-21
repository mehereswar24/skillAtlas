SELECT department, employee, salary
FROM (
  SELECT department, employee, salary,
         DENSE_RANK() OVER (
           PARTITION BY department ORDER BY salary DESC
         ) AS rnk
  FROM salaries
)
WHERE rnk = 2
ORDER BY department, employee
