package vn.edu.hcmiu.sla.auth;

import java.time.LocalDateTime;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Changes to the logged-in person's own account (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5). */
@Service
public class Accounts {

    private final UserRepository users;

    public Accounts(UserRepository users) {
        this.users = users;
    }

    /** users.last_login_at, for the Users page (stage 2) and Profile. */
    @Transactional
    public void loggedIn(Integer userId, LocalDateTime now) {
        users.findById(userId).ifPresent(user -> user.loggedIn(now));
    }
}
