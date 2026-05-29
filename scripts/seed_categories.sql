-- Seed the distinct categories used by the existing books dataset.
-- Run this after the categories table exists.

INSERT INTO categories (id, name)
VALUES
    ('6c9b5e2a-0d1f-4d4f-8f01-000000000001', 'Classics & Literature'),
    ('6c9b5e2a-0d1f-4d4f-8f01-000000000002', 'Sci-Fi, Fantasy, & Dystopian'),
    ('6c9b5e2a-0d1f-4d4f-8f01-000000000003', 'Thriller, Mystery, & Modern Fiction'),
    ('6c9b5e2a-0d1f-4d4f-8f01-000000000004', 'Non-Fiction, Philosophy, & Self-Help')
ON CONFLICT (name) DO NOTHING;