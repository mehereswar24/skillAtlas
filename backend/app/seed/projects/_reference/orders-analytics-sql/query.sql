SELECT
  c.name                           AS name,
  COUNT(DISTINCT o.id)             AS order_count,
  SUM(oi.quantity * oi.unit_price) AS total_spend
FROM customers c
JOIN orders o       ON o.customer_id = c.id
JOIN order_items oi ON oi.order_id = o.id
GROUP BY c.id, c.name
ORDER BY total_spend DESC, name
