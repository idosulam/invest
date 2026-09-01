-- Development seed data
-- Run: make db-shell < db/seeds/dev_seed.sql

-- Create admin user (password: admin123 — CHANGE IN PRODUCTION)
-- Argon2 hash of 'admin123'
INSERT INTO users (id, email, username, password_hash, role, is_active, created_at, updated_at)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'admin@market-platform.local',
    'admin',
    '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$somehash',  -- placeholder, generate real hash
    'ADMIN',
    true,
    NOW(),
    NOW()
) ON CONFLICT (email) DO NOTHING;

-- Sample instruments
INSERT INTO instruments (id, symbol, name, type, currency, status, exchange, sector, country, created_at, updated_at)
VALUES
    ('b0000000-0000-0000-0000-000000000001', 'AAPL', 'Apple Inc.', 'STOCK', 'USD', 'ACTIVE', 'NASDAQ', 'Technology', 'US', NOW(), NOW()),
    ('b0000000-0000-0000-0000-000000000002', 'MSFT', 'Microsoft Corporation', 'STOCK', 'USD', 'ACTIVE', 'NASDAQ', 'Technology', 'US', NOW(), NOW()),
    ('b0000000-0000-0000-0000-000000000003', 'GOOGL', 'Alphabet Inc.', 'STOCK', 'USD', 'ACTIVE', 'NASDAQ', 'Technology', 'US', NOW(), NOW()),
    ('b0000000-0000-0000-0000-000000000004', 'AMZN', 'Amazon.com Inc.', 'STOCK', 'USD', 'ACTIVE', 'NASDAQ', 'Consumer Cyclical', 'US', NOW(), NOW()),
    ('b0000000-0000-0000-0000-000000000005', 'TSLA', 'Tesla Inc.', 'STOCK', 'USD', 'ACTIVE', 'NASDAQ', 'Consumer Cyclical', 'US', NOW(), NOW()),
    ('b0000000-0000-0000-0000-000000000006', 'SPY', 'SPDR S&P 500 ETF Trust', 'ETF', 'USD', 'ACTIVE', 'NYSE', NULL, 'US', NOW(), NOW()),
    ('b0000000-0000-0000-0000-000000000007', 'QQQ', 'Invesco QQQ Trust', 'ETF', 'USD', 'ACTIVE', 'NASDAQ', NULL, 'US', NOW(), NOW()),
    ('b0000000-0000-0000-0000-000000000008', 'VTI', 'Vanguard Total Stock Market ETF', 'ETF', 'USD', 'ACTIVE', 'NYSE', NULL, 'US', NOW(), NOW()),
    ('b0000000-0000-0000-0000-000000000009', '^GSPC', 'S&P 500 Index', 'BENCHMARK', 'USD', 'ACTIVE', 'NYSE', NULL, 'US', NOW(), NOW()),
    ('b0000000-0000-0000-0000-000000000010', '^DJI', 'Dow Jones Industrial Average', 'BENCHMARK', 'USD', 'ACTIVE', 'NYSE', NULL, 'US', NOW(), NOW())
ON CONFLICT (symbol, venue_id) DO NOTHING;

-- Sample watchlist
INSERT INTO watchlists (id, name, owner_id, instrument_ids, created_at, updated_at)
VALUES (
    'c0000000-0000-0000-0000-000000000001',
    'Tech Stocks',
    'a0000000-0000-0000-0000-000000000001',
    '["b0000000-0000-0000-0000-000000000001", "b0000000-0000-0000-0000-000000000002", "b0000000-0000-0000-0000-000000000003"]',
    NOW(),
    NOW()
) ON CONFLICT DO NOTHING;
