SELECT e.name AS name, gm.name AS skip_level_manager
FROM employees e
LEFT JOIN employees m  ON m.id = e.manager_id
LEFT JOIN employees gm ON gm.id = m.manager_id
ORDER BY e.id
