SELECT sale_date,
       SUM(revenue) AS daily_total,
       SUM(SUM(revenue)) OVER (ORDER BY sale_date) AS running_total
FROM sales
GROUP BY sale_date
ORDER BY sale_date
