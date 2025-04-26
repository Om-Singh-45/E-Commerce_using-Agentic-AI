-- Migration script to add category field to Product table

-- Add the category column to the Product table
ALTER TABLE product ADD COLUMN category VARCHAR(50);

-- Update existing products with default categories based on name (examples)
-- This is optional and can be customized based on your existing data
UPDATE product SET category = 'Phone' WHERE name LIKE '%phone%' OR description LIKE '%phone%';
UPDATE product SET category = 'Laptop' WHERE name LIKE '%laptop%' OR description LIKE '%laptop%';
UPDATE product SET category = 'Headphone' WHERE name LIKE '%headphone%' OR description LIKE '%headphone%';
UPDATE product SET category = 'Tablet' WHERE name LIKE '%tablet%' OR description LIKE '%tablet%';
UPDATE product SET category = 'Watch' WHERE name LIKE '%watch%' OR description LIKE '%watch%';
UPDATE product SET category = 'Camera' WHERE name LIKE '%camera%' OR description LIKE '%camera%';
UPDATE product SET category = 'TV' WHERE name LIKE '%tv%' OR name LIKE '%television%';
UPDATE product SET category = 'Gaming' WHERE name LIKE '%game%' OR name LIKE '%gaming%';
UPDATE product SET category = 'Books' WHERE name LIKE '%book%';
-- Set any remaining products to 'Other'
UPDATE product SET category = 'Other' WHERE category IS NULL; 