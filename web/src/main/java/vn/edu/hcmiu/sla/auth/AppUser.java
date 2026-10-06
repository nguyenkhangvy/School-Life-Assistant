package vn.edu.hcmiu.sla.auth;

import java.util.Collection;
import java.util.List;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

/**
 * The logged-in user as Spring Security keeps it. Controllers get it with
 * {@code @AuthenticationPrincipal AppUser user} and filter every query by {@code user.id()}. Its role is its one
 * authority (ROLE_STUDENT, ROLE_AUDITOR or ROLE_ADMIN).
 */
public record AppUser(Integer id, String email, String displayName, String passwordHash, Role role, boolean active)
        implements UserDetails {

    public static AppUser of(User user) {
        return new AppUser(user.getId(), user.getEmail(), user.getDisplayName(), user.getPasswordHash(), user.getRole(),
                user.isActive());
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return List.of(new SimpleGrantedAuthority(role.authority()));
    }

    /** False once deactivated: login then refuses the account, but only after the right password (SecurityConfig). */
    @Override
    public boolean isEnabled() {
        return active;
    }

    @Override
    public String getPassword() {
        return passwordHash;
    }

    @Override
    public String getUsername() {
        return email;
    }

    /** For templates: {@code ${#authentication.principal.displayName}}. */
    public String getDisplayName() {
        return displayName;
    }
}
