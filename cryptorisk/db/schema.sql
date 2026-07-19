CREATE DATABASE IF NOT EXISTS cryptorisk;

USE cryptorisk;


CREATE TABLE IF NOT EXISTS users (
    userid INT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(50) NOT NULL,
    balance DECIMAL(12,2) NOT NULL
);


CREATE TABLE IF NOT EXISTS portfolio (
    userid INT,
    coin VARCHAR(50) NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    buy_price DECIMAL(12,5) NOT NULL,

    PRIMARY KEY (userid, coin),

    FOREIGN KEY (userid)
    REFERENCES users(userid)
);


CREATE TABLE IF NOT EXISTS transactions (
    transid INT PRIMARY KEY,
    userid INT NOT NULL,
    coin VARCHAR(50) NOT NULL,
    action ENUM('BUY','SELL') NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(12,5) NOT NULL,
    trade_date DATE NOT NULL,

    FOREIGN KEY (userid)
    REFERENCES users(userid)
);

INSERT IGNORE INTO users
(userid, username, password, balance)
VALUES
(1, 'alice', 'alice123', 10000.00),
(2, 'bob', 'bobpass', 7450.50),
(3, 'charlie', 'charliepw', 12300.75),
(4, 'diana', 'dianapass', 9875.25);


INSERT IGNORE INTO portfolio
(userid, coin, quantity, buy_price)
VALUES
(1, 'BTC', 0.15, 43250.00),
(1, 'ETH', 2.40, 2410.50),
(2, 'DOGE', 15000.00, 0.16),
(2, 'SOL', 18.50, 142.30),
(3, 'BTC', 0.05, 41800.00),
(3, 'SOL', 40.00, 138.75),
(4, 'ETH', 1.20, 2380.00),
(4, 'DOGE', 8000.00, 0.15);


INSERT IGNORE INTO transactions
(transid, userid, coin, action, quantity, price, trade_date)
VALUES
(1, 1, 'BTC', 'BUY', 0.10, 42000.00, '2026-06-28'),
(2, 1, 'BTC', 'BUY', 0.05, 43250.00, '2026-07-03'),
(3, 1, 'ETH', 'BUY', 2.40, 2410.50, '2026-07-05'),

(4, 2, 'DOGE', 'BUY', 20000.00, 0.14, '2026-06-30'),
(5, 2, 'DOGE', 'SELL', 5000.00, 0.17, '2026-07-06'),
(6, 2, 'SOL', 'BUY', 18.50, 142.30, '2026-07-08'),

(7, 3, 'BTC', 'BUY', 0.05, 41800.00, '2026-07-01'),
(8, 3, 'SOL', 'BUY', 40.00, 138.75, '2026-07-04'),

(9, 4, 'ETH', 'BUY', 1.50, 2350.00, '2026-06-29'),
(10, 4, 'ETH', 'SELL', 0.30, 2450.00, '2026-07-09'),

(11, 4, 'DOGE', 'BUY', 8000.00, 0.15, '2026-07-10');
