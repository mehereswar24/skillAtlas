SELECT product,
  SUM(CASE WHEN month = 'Jan' THEN amount ELSE 0 END) AS jan_total,
  SUM(CASE WHEN month = 'Feb' THEN amount ELSE 0 END) AS feb_total,
  SUM(CASE WHEN month = 'Mar' THEN amount ELSE 0 END) AS mar_total
FROM monthly_sales
GROUP BY product
ORDER BY product
