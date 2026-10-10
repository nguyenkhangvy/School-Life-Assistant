package vn.edu.hcmiu.sla.auth;

import java.time.LocalDateTime;
import java.util.Optional;

import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Changes to the logged-in person's own account (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5). */
@Service
public class Accounts {

    private final UserRepository users;
    private final PasswordEncoder passwords;

    public Accounts(UserRepository users, PasswordEncoder passwords) {
        this.users = users;
        this.passwords = passwords;
    }

    /** users.last_login_at, for the Users page (stage 2) and Profile; the account as now saved. */
    @Transactional
    public Optional<User> loggedIn(Integer userId, LocalDateTime now) {
        Optional<User> user = users.findById(userId);
        user.ifPresent(account -> account.loggedIn(now));
        return user;
    }

    /**
     * Spring calls this at login when the stored hash is an older kind than Argon2id (security hardening spec, 4): the
     * same password, hashed anew. Not a change by anyone, so updated_at stays.
     */
    @Transactional
    public UserDetails rehash(UserDetails account, String newHash) {
        User user = users.findById(((AppUser) account).id()).orElseThrow();
        user.rehash(newHash);
        return AppUser.of(user);
    }

    /** A new display name and email, both already checked by the Profile page (spec 5.4). */
    @Transactional
    public void changeProfile(Integer userId, String displayName, String email, LocalDateTime now) {
        users.findById(userId).orElseThrow().changeProfile(displayName, email, userId, now);
    }

    /** A new password the person chose themselves (spec 5.5); the account as saved. */
    @Transactional
    public User changePassword(Integer userId, String password, LocalDateTime now) {
        User user = users.findById(userId).orElseThrow();
        user.changePassword(passwords.encode(password), userId, now);
        return user;
    }
}
