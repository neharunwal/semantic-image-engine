-- schema.sql: MySQL 8.0+ Relational Schema for Cloud or Local Server Deployments
CREATE DATABASE IF NOT EXISTS semantic_media_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE semantic_media_db;

CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INT NOT NULL,
    permission_id INT NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role_id INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

CREATE TABLE IF NOT EXISTS archetypes (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category ENUM('studio', 'sunset', 'beach', 'monument', 'wedding', 'custom') NOT NULL,
    parameters_json JSON NOT NULL,
    preview_url VARCHAR(500),
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS processed_photos (
    id VARCHAR(64) PRIMARY KEY,
    user_id INT NOT NULL,
    original_filename VARCHAR(255),
    original_size_bytes BIGINT NOT NULL,
    manifest_size_bytes INT NOT NULL,
    mode ENUM('forensic', 'semantic') NOT NULL,
    archetype_id VARCHAR(64),
    manifest_data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Seed Initial Super Admin
INSERT IGNORE INTO roles (id, name, description) VALUES 
(1, 'super_admin', 'Full platform administrator with all CRUD privileges'),
(2, 'user', 'Standard user who can encode and decode photos');

INSERT IGNORE INTO users (email, password_hash, role_id) VALUES
('nehasb25@gmail.com', '$2b$12$e8YmGkC3t8.kQvK4V97Zuu3xU9qZqF8b2d4j6k8l0m2n4p6r8t0v.', 1);
