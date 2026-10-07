package vn.edu.hcmiu.sla.auth;

import java.io.IOException;
import java.time.Clock;
import java.time.LocalDateTime;

import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.core.Authentication;
import org.springframework.security.web.authentication.SavedRequestAwareAuthenticationSuccessHandler;
import org.springframework.stereotype.Component;

import vn.edu.hcmiu.sla.core.ClientAddress;

/**
 * After a login: this email from this IP starts its count again (LoginLimits), the login's time is noted, then the
 * browser goes back to the page that asked for login, else home, as Spring Security's own handler does.
 */
@Component
public class LoggedIn extends SavedRequestAwareAuthenticationSuccessHandler {

    private final Accounts accounts;
    private final LoginLimits limits;
    private final Clock clock;

    public LoggedIn(Accounts accounts, LoginLimits limits, Clock clock) {
        this.accounts = accounts;
        this.limits = limits;
        this.clock = clock;
        setDefaultTargetUrl("/");
    }

    @Override
    public void onAuthenticationSuccess(HttpServletRequest request, HttpServletResponse response,
            Authentication authentication) throws IOException, ServletException {
        if (authentication.getPrincipal() instanceof AppUser user) {
            limits.succeeded(user.email(), ClientAddress.of(request));
            accounts.loggedIn(user.id(), LocalDateTime.now(clock));
        }
        super.onAuthenticationSuccess(request, response, authentication);
    }
}
