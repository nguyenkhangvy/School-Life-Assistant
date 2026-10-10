package vn.edu.hcmiu.sla.auth;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.stereotype.Component;

/**
 * Logs a person in for this browser, as the login form does: a new session id, then the account saved in the session.
 * Register uses it for a new account; Password uses it so the session that changed the password stays logged in
 * (AccountCheck logs out the others).
 */
@Component
public class Sessions {

    private final SecurityContextRepository logins;

    public Sessions(SecurityContextRepository logins) {
        this.logins = logins;
    }

    public void logIn(AppUser user, HttpServletRequest request, HttpServletResponse response) {
        if (request.getSession(false) != null) {
            request.changeSessionId(); // a new session id after login
        }
        refresh(user, request, response);
    }

    /**
     * Puts the account as now saved into this browser's session, keeping its session id: after a login whose password
     * was just re-hashed (security hardening spec, 4), so AccountCheck doesn't take the new hash for a changed password.
     */
    public void refresh(AppUser user, HttpServletRequest request, HttpServletResponse response) {
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(UsernamePasswordAuthenticationToken.authenticated(user, null, user.getAuthorities()));
        SecurityContextHolder.setContext(context);
        logins.saveContext(context, request, response);
    }
}
