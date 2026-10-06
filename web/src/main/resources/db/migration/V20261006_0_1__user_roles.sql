-- Site roles and soft delete (docs/superpowers/specs/2026-10-06-site-roles-design.md, 3.1). Module 0 is Site: tables
-- every module shares. Every account so far becomes an active Student, last changed when it was made. MySQL refuses a
-- CHECK on a column whose foreign key has an ON DELETE action, so only role has one: "deactivated_by is set when
-- deactivated_at is" is kept by User.
ALTER TABLE users ADD COLUMN role VARCHAR(7) NOT NULL DEFAULT 'student';
ALTER TABLE users ADD COLUMN created_by INT NULL;
ALTER TABLE users ADD COLUMN updated_at DATETIME NULL;
ALTER TABLE users ADD COLUMN updated_by INT NULL;
ALTER TABLE users ADD COLUMN deactivated_at DATETIME NULL;
ALTER TABLE users ADD COLUMN deactivated_by INT NULL;
ALTER TABLE users ADD COLUMN last_login_at DATETIME NULL;
ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE users SET updated_at = created_at;
ALTER TABLE users MODIFY updated_at DATETIME NOT NULL;
ALTER TABLE users ADD CONSTRAINT ck_users_role CHECK (role IN ('student', 'auditor', 'admin'));
ALTER TABLE users ADD CONSTRAINT fk_users_created_by FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL;
ALTER TABLE users ADD CONSTRAINT fk_users_updated_by FOREIGN KEY (updated_by) REFERENCES users (id) ON DELETE SET NULL;
ALTER TABLE users ADD CONSTRAINT fk_users_deactivated_by
    FOREIGN KEY (deactivated_by) REFERENCES users (id) ON DELETE SET NULL;
CREATE INDEX ix_users_role ON users (role);
CREATE INDEX ix_users_created_at ON users (created_at);
CREATE INDEX ix_users_last_login_at ON users (last_login_at);
