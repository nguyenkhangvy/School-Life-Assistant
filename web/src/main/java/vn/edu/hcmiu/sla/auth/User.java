package vn.edu.hcmiu.sla.auth;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * An account. Shared by every module: their tables point at users.id. Its role, whether it is active and who last
 * changed it: docs/superpowers/specs/2026-10-06-site-roles-design.md, 3.1. In the changes below, by is the account that
 * made the change; null means the site itself (the first Admin, from SITE_ADMIN_EMAIL).
 */
@Entity
@Table(name = "users")
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(nullable = false, unique = true, length = 255)
    private String email;

    @Column(name = "display_name", nullable = false, length = 100)
    private String displayName;

    @Column(name = "password_hash", nullable = false, length = 255)
    private String passwordHash;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt; // UTC

    @Column(nullable = false, length = 7)
    private String role = Role.STUDENT.code();

    @Column(name = "created_by")
    private Integer createdBy; // the Admin who made the account; null = registered themselves

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt; // UTC

    @Column(name = "updated_by")
    private Integer updatedBy; // who made the last change; null = the site, or none since

    @Column(name = "deactivated_at")
    private LocalDateTime deactivatedAt; // UTC; null = active

    @Column(name = "deactivated_by")
    private Integer deactivatedBy;

    @Column(name = "last_login_at")
    private LocalDateTime lastLoginAt; // UTC

    @Column(name = "must_change_password", nullable = false)
    private boolean mustChangePassword;

    protected User() {
    }

    /** An active Student, as register makes one. */
    public User(String email, String displayName, String passwordHash, LocalDateTime createdAt) {
        this.email = email;
        this.displayName = displayName;
        this.passwordHash = passwordHash;
        this.createdAt = createdAt;
        this.updatedAt = createdAt;
    }

    public Integer getId() {
        return id;
    }

    public String getEmail() {
        return email;
    }

    public String getDisplayName() {
        return displayName;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public Role getRole() {
        return Role.of(role);
    }

    public Integer getCreatedBy() {
        return createdBy;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public Integer getUpdatedBy() {
        return updatedBy;
    }

    public LocalDateTime getDeactivatedAt() {
        return deactivatedAt;
    }

    public Integer getDeactivatedBy() {
        return deactivatedBy;
    }

    public LocalDateTime getLastLoginAt() {
        return lastLoginAt;
    }

    public boolean isMustChangePassword() {
        return mustChangePassword;
    }

    /** Not deactivated. */
    public boolean isActive() {
        return deactivatedAt == null;
    }

    /** Allowed to sync a laptop and seen by other students (spec 4.6 and 5.2). */
    public boolean isActiveStudent() {
        return isActive() && getRole() == Role.STUDENT;
    }

    public void changeRole(Role newRole, Integer by, LocalDateTime now) {
        role = newRole.code();
        changed(by, now);
    }

    public void deactivate(Integer by, LocalDateTime now) {
        deactivatedAt = now;
        deactivatedBy = by;
        changed(by, now);
    }

    public void reactivate(Integer by, LocalDateTime now) {
        deactivatedAt = null;
        deactivatedBy = null;
        changed(by, now);
    }

    public void changeProfile(String newDisplayName, String newEmail, Integer by, LocalDateTime now) {
        displayName = newDisplayName;
        email = newEmail;
        changed(by, now);
    }

    /** A password the person chose themselves, so they no longer have to change it. */
    public void changePassword(String newPasswordHash, Integer by, LocalDateTime now) {
        passwordHash = newPasswordHash;
        mustChangePassword = false;
        changed(by, now);
    }

    /** The same password hashed anew, with a stronger algorithm: not a change by anyone, so updated_at stays. */
    public void rehash(String newPasswordHash) {
        passwordHash = newPasswordHash;
    }

    /** A login isn't a change to the account: updated_at stays. */
    public void loggedIn(LocalDateTime now) {
        lastLoginAt = now;
    }

    private void changed(Integer by, LocalDateTime now) {
        updatedAt = now;
        updatedBy = by;
    }
}
