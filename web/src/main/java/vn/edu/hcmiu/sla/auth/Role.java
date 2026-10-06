package vn.edu.hcmiu.sla.auth;

/**
 * An account's role, one per account (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.1): Students use
 * School, Groups and Friends; Auditors read the audit log and statistics; Admins manage accounts. users.role keeps the
 * code ("student"); Spring Security sees the authority (ROLE_STUDENT), so hasRole("STUDENT") matches it.
 */
public enum Role {
    STUDENT("student", "Student"),
    AUDITOR("auditor", "Auditor"),
    ADMIN("admin", "Admin");

    private final String code;
    private final String label;

    Role(String code, String label) {
        this.code = code;
        this.label = label;
    }

    /** As stored in users.role. */
    public String code() {
        return code;
    }

    /** As pages show it: "Student". */
    public String label() {
        return label;
    }

    public String authority() {
        return "ROLE_" + name();
    }

    public static Role of(String code) {
        for (Role role : values()) {
            if (role.code.equals(code)) {
                return role;
            }
        }
        throw new IllegalArgumentException("Not a role: " + code);
    }
}
