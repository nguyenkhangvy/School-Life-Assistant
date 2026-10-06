package vn.edu.hcmiu.sla.auth;

import java.time.Clock;
import java.time.LocalDateTime;
import java.util.Optional;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

/**
 * The first Admin (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5.3). Each time the site starts, after the
 * migrations: if it has no active Admin, the account named by SITE_ADMIN_EMAIL (.env) becomes one. Once an Admin
 * exists the setting does nothing, so it never undoes an Admin's decisions; it is also the way back if every Admin is
 * ever lost.
 */
@Component
class FirstAdmin implements ApplicationRunner {

    /** What a start did with the setting. */
    enum Outcome { NO_SETTING, ADMIN_EXISTS, NO_ACCOUNT, MADE_ADMIN }

    private static final Logger LOG = LoggerFactory.getLogger(FirstAdmin.class);

    private final UserRepository users;
    private final Clock clock;
    private final String email;

    FirstAdmin(UserRepository users, Clock clock, @Value("${SITE_ADMIN_EMAIL:}") String email) {
        this.users = users;
        this.clock = clock;
        this.email = email;
    }

    @Override
    public void run(ApplicationArguments args) {
        promote();
    }

    Outcome promote() {
        String wanted = AppUserDetailsService.normalizeEmail(email);
        if (wanted.isEmpty()) {
            return Outcome.NO_SETTING;
        }
        if (users.existsByRoleAndDeactivatedAtIsNull(Role.ADMIN.code())) {
            return Outcome.ADMIN_EXISTS;
        }
        Optional<User> account = users.findByEmail(wanted);
        if (account.isEmpty()) {
            LOG.warn("SITE_ADMIN_EMAIL names no account: {}. Register it on the site, then restart.", wanted);
            return Outcome.NO_ACCOUNT;
        }
        User admin = account.get();
        LocalDateTime now = LocalDateTime.now(clock);
        if (!admin.isActive()) {
            admin.reactivate(null, now);
        }
        admin.changeRole(Role.ADMIN, null, now);
        users.save(admin);
        LOG.info("Made {} an Admin (SITE_ADMIN_EMAIL)", wanted);
        return Outcome.MADE_ADMIN;
    }
}
