SELECT sku FROM products WHERE stock = 0
UNION
SELECT sku FROM products WHERE recalled = 1
ORDER BY sku
