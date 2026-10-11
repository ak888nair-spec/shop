DROP DATABASE IF EXISTS shop;
CREATE DATABASE shop;
USE shop;

CREATE TABLE Admin (
  Admin_ID INT PRIMARY KEY,
  Name VARCHAR(100) NOT NULL,
  Phone_no VARCHAR(15),
  Address VARCHAR(255)
);

CREATE TABLE Supplier (
  Supplier_ID INT PRIMARY KEY,
  Name VARCHAR(100) NOT NULL,
  Phone_no VARCHAR(15),
  Address VARCHAR(255)
);

CREATE TABLE Category (
  Category_name VARCHAR(50) PRIMARY KEY
);

CREATE TABLE Customer (
  Customer_ID INT PRIMARY KEY,
  Name VARCHAR(100) NOT NULL,
  Phone_no VARCHAR(15) UNIQUE,
  Email VARCHAR(100),
  Address VARCHAR(255)
);

CREATE TABLE Product (
  Item_code INT PRIMARY KEY,
  Item_name VARCHAR(100) NOT NULL,
  Details VARCHAR(255),
  Price DECIMAL(10,2),
  Supplier_ID INT,
  Admin_ID INT,
  FOREIGN KEY (Supplier_ID) REFERENCES Supplier(Supplier_ID),
  FOREIGN KEY (Admin_ID) REFERENCES Admin(Admin_ID)
);

CREATE TABLE Product_Category (
  Item_code INT,
  Category_name VARCHAR(50),
  PRIMARY KEY (Item_code, Category_name),
  FOREIGN KEY (Item_code) REFERENCES Product(Item_code),
  FOREIGN KEY (Category_name) REFERENCES Category(Category_name)
);

CREATE TABLE Cart (
  Customer_ID INT,
  Cart_ID INT,
  PRIMARY KEY (Customer_ID, Cart_ID),
  UNIQUE (Customer_ID),
  FOREIGN KEY (Customer_ID) REFERENCES Customer(Customer_ID)
);

CREATE TABLE Cart_Item (
  Customer_ID INT,
  Cart_ID INT,
  Item_code INT,
  Quantity INT NOT NULL DEFAULT 1,
  PRIMARY KEY (Customer_ID, Cart_ID, Item_code),
  FOREIGN KEY (Customer_ID, Cart_ID) REFERENCES Cart(Customer_ID, Cart_ID),
  FOREIGN KEY (Item_code) REFERENCES Product(Item_code)
);

CREATE TABLE Orders (
  Order_ID INT PRIMARY KEY,
  Amount DECIMAL(10,2),
  Status VARCHAR(30),
  Customer_ID INT NOT NULL,
  Admin_ID INT,
  Delivered_To_ID INT,
  Returned_By_ID INT,
  FOREIGN KEY (Customer_ID) REFERENCES Customer(Customer_ID),
  FOREIGN KEY (Admin_ID) REFERENCES Admin(Admin_ID),
  FOREIGN KEY (Delivered_To_ID) REFERENCES Customer(Customer_ID),
  FOREIGN KEY (Returned_By_ID) REFERENCES Customer(Customer_ID)
);

CREATE TABLE Order_Item (
  Order_ID INT,
  Item_code INT,
  Quantity INT NOT NULL DEFAULT 1,
  PRIMARY KEY (Order_ID, Item_code),
  FOREIGN KEY (Order_ID) REFERENCES Orders(Order_ID),
  FOREIGN KEY (Item_code) REFERENCES Product(Item_code)
);

CREATE TABLE Backorder (
  Order_ID INT,
  Item_code INT,
  Expected_Date DATE,
  PRIMARY KEY (Order_ID, Item_code),
  FOREIGN KEY (Order_ID) REFERENCES Orders(Order_ID),
  FOREIGN KEY (Item_code) REFERENCES Product(Item_code)
);

CREATE TABLE Review (
  Customer_ID INT,
  Item_code INT,
  Rating INT CHECK (Rating BETWEEN 1 AND 5),
  Comment VARCHAR(500),
  PRIMARY KEY (Customer_ID, Item_code),
  FOREIGN KEY (Customer_ID) REFERENCES Customer(Customer_ID),
  FOREIGN KEY (Item_code) REFERENCES Product(Item_code)
);

CREATE TABLE Payment (
  Order_ID INT,
  Payment_ID INT,
  Amount DECIMAL(10,2),
  Customer_ID INT NOT NULL,
  Refunded_To_ID INT,
  PRIMARY KEY (Order_ID, Payment_ID),
  FOREIGN KEY (Order_ID) REFERENCES Orders(Order_ID),
  FOREIGN KEY (Customer_ID) REFERENCES Customer(Customer_ID),
  FOREIGN KEY (Refunded_To_ID) REFERENCES Customer(Customer_ID)
);