-- Seed authors into the authors table.
-- IDs are provided explicitly because the migration does not define a DB default.

INSERT INTO authors (id, name, bio)
VALUES
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000001', 'Morgan Reed', 'Writes about API design and service boundaries.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000002', 'Ava Patel', 'Focuses on data modeling and database performance.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000003', 'Liam Chen', 'Covers Python async patterns and performance.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000004', 'Isabella Torres', 'Specializes in security and authentication.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000005', 'Noah Singh', 'Writes about testing and CI/CD workflows.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000006', 'Emma Brooks', 'Focuses on observability and monitoring.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000007', 'Oliver Park', 'Covers distributed systems and scaling.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000008', 'Sophia Kim', 'Writes about FastAPI and production operations.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000009', 'Ethan Walsh', 'Specializes in caching and performance tuning.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-00000000000a', 'Mia Rivera', 'Focuses on schema design and data validation.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-00000000000b', 'Lucas Grant', 'Covers containerization and deployment.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-00000000000c', 'Harper Lee', 'Writes about API documentation and OpenAPI.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-00000000000d', 'Elijah Moore', 'Focuses on resilience and error handling.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-00000000000e', 'Amelia Scott', 'Covers domain-driven design and service layers.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-00000000000f', 'James Foster', 'Writes about SQL performance and indexing.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000010', 'Charlotte King', 'Focuses on testing strategies for APIs.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000011', 'Benjamin Young', 'Covers event-driven systems and queues.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000012', 'Evelyn Price', 'Writes about configuration and secrets management.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000013', 'Henry Adams', 'Focuses on pagination, sorting, and search.'),
    ('7b1a2c3d-4e5f-4a6b-9c01-000000000014', 'Abigail Turner', 'Covers security reviews and threat modeling.');
