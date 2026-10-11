USE shop;
INSERT INTO Admin (Admin_ID, Name) VALUES (1, 'Rahul');
INSERT INTO Supplier (Supplier_ID, Name) VALUES (1, 'Northwind Trading'), (2, 'Pagepoint Books'), (3, 'HomeNest'), (4, 'Stridewear');
INSERT INTO Category (Category_name) VALUES ('Electronics'), ('Books'), ('Home & Kitchen'), ('Fashion'), ('Beauty'), ('Sports & Outdoors'), ('Toys & Games'), ('Grocery'), ('Other');
INSERT INTO Product (Item_code, Item_name, Details, Price, Stock, Expected_Date, Supplier_ID, Admin_ID) VALUES
(101, 'Wireless Earbuds', 'Bluetooth 5.3 earbuds with a charging case, up to 24 hours of battery in total.', 1999.00, 25, NULL, 1, 1),
(102, 'Bluetooth Speaker', 'Portable water-resistant speaker with deep bass and 12 hours of playtime.', 2499.00, 12, NULL, 1, 1),
(103, '20000 mAh Power Bank', 'Slim power bank with two USB ports and fast charging for phones and tablets.', 1499.00, 0, DATE_ADD(CURDATE(), INTERVAL 5 DAY), 1, 1),
(104, 'USB-C Fast Charger 65W', 'Compact wall charger for laptops, tablets and phones.', 1299.00, 40, NULL, 1, 1),
(105, 'Ground Coffee, 250 g', 'Medium roast ground coffee with a smooth, chocolatey finish.', 399.00, 60, NULL, 1, 1),
(106, 'Mixed Nuts, 500 g', 'Roasted almonds, cashews and pistachios, lightly salted.', 549.00, 35, NULL, 1, 1),
(107, 'Wooden Chess Set', 'Hand-finished wooden board with weighted pieces and a storage drawer.', 799.00, 14, NULL, 1, 1),
(108, 'Jigsaw Puzzle, 1000 pieces', 'A scenic mountain lake puzzle with thick, glare-free pieces.', 499.00, 0, DATE_ADD(CURDATE(), INTERVAL 7 DAY), 1, 1),
(109, 'Python Programming Handbook', 'A clear, example-driven guide for beginners moving to real projects.', 549.00, 30, NULL, 2, 1),
(110, 'The Quiet Lighthouse', 'A slow-burning coastal mystery novel about a keeper and a missing letter.', 299.00, 18, NULL, 2, 1),
(111, 'Illustrated World Atlas', 'Hardcover atlas with detailed maps, flags and country facts.', 899.00, 0, DATE_ADD(CURDATE(), INTERVAL 10 DAY), 2, 1),
(112, 'Stainless Steel Water Bottle, 1 L', 'Double-walled bottle that keeps drinks cold for 24 hours or hot for 12.', 599.00, 45, NULL, 3, 1),
(113, 'Non-Stick Frying Pan, 24 cm', 'Even-heating pan with a cool-touch handle, works on gas and induction.', 899.00, 20, NULL, 3, 1),
(114, 'Cotton Bedsheet, Double', 'Soft 180 thread count cotton sheet with two matching pillow covers.', 1199.00, 16, NULL, 3, 1),
(115, 'LED Desk Lamp', 'Dimmable desk lamp with three colour modes and a USB charging port.', 799.00, 22, NULL, 3, 1),
(116, 'Cotton Crew-Neck T-Shirt', 'Everyday regular-fit tee in breathable combed cotton.', 399.00, 70, NULL, 4, 1),
(117, 'Running Shoes', 'Lightweight mesh trainers with a cushioned sole for daily runs.', 2299.00, 15, NULL, 4, 1),
(118, 'Canvas Backpack, 25 L', 'Roomy backpack with a padded laptop sleeve and water bottle pockets.', 1099.00, 0, DATE_ADD(CURDATE(), INTERVAL 4 DAY), 4, 1),
(119, 'Yoga Mat, 6 mm', 'Non-slip, easy-to-clean mat with a carry strap.', 699.00, 28, NULL, 4, 1),
(120, 'Moisturising Face Cream, 100 ml', 'Light daily cream with aloe and vitamin E for all skin types.', 349.00, 50, NULL, 3, 1);
INSERT INTO Product_Category (Item_code, Category_name) VALUES
(101, 'Electronics'), (102, 'Electronics'), (103, 'Electronics'), (104, 'Electronics'),
(105, 'Grocery'), (106, 'Grocery'), (107, 'Toys & Games'), (108, 'Toys & Games'),
(109, 'Books'), (110, 'Books'), (111, 'Books'),
(112, 'Home & Kitchen'), (113, 'Home & Kitchen'), (114, 'Home & Kitchen'), (115, 'Home & Kitchen'),
(116, 'Fashion'), (117, 'Fashion'), (118, 'Fashion'), (119, 'Sports & Outdoors'), (120, 'Beauty');
INSERT INTO Customer (Customer_ID, Name, Phone_no) VALUES (1, 'Asha', '9999999999');