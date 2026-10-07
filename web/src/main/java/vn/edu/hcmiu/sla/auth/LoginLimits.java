package vn.edu.hcmiu.sla.auth;

import java.time.Duration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import vn.edu.hcmiu.sla.core.Attempts;

/**
 * The two login rules (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.3): 5 wrong passwords for one
 * email from one IP, or 100 from one IP for any emails, within 15 minutes, and the password isn't checked until the
 * count drops. An unknown email counts like a wrong password, so the limits never show which emails have accounts.
 */
@Component
public class LoginLimits {

    static final int PER_PAIR = 5;
    static final int PER_IP = 100;
    static final Duration WINDOW = Duration.ofMinutes(15);

    private static final Logger LOG = LoggerFactory.getLogger(LoginLimits.class);

    private final Attempts attempts;

    public LoginLimits(Attempts attempts) {
        this.attempts = attempts;
    }

    /** How long this email from this IP must wait before its password is checked; zero: check it now. */
    public Duration waitFor(String email, String ip) {
        Duration pair = attempts.waitFor(pairKey(email, ip), PER_PAIR, WINDOW);
        Duration all = attempts.waitFor(ipKey(ip), PER_IP, WINDOW);
        return pair.compareTo(all) >= 0 ? pair : all;
    }

    /** A wrong password or an unknown email. */
    public void failed(String email, String ip) {
        attempts.add(pairKey(email, ip));
        attempts.add(ipKey(ip));
        if (attempts.count(pairKey(email, ip), WINDOW) == PER_PAIR) {
            LOG.warn("Login limit reached for {} (one email from one IP)", ip);
        }
        if (attempts.count(ipKey(ip), WINDOW) == PER_IP) {
            LOG.warn("Login limit reached for {} (one IP, any emails)", ip);
        }
    }

    /** The right password: this email from this IP starts again. */
    public void succeeded(String email, String ip) {
        attempts.clear(pairKey(email, ip));
    }

    private static String pairKey(String email, String ip) {
        return "login-pair:" + AppUserDetailsService.normalizeEmail(email) + "|" + ip;
    }

    private static String ipKey(String ip) {
        return "login-ip:" + ip;
    }
}
