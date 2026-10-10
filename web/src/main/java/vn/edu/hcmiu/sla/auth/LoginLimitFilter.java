package vn.edu.hcmiu.sla.auth;

import java.io.IOException;
import java.time.Duration;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.http.HttpMethod;
import org.springframework.security.web.servlet.util.matcher.PathPatternRequestMatcher;
import org.springframework.security.web.util.matcher.RequestMatcher;
import org.springframework.web.filter.OncePerRequestFilter;

import vn.edu.hcmiu.sla.core.Attempts;
import vn.edu.hcmiu.sla.core.ClientAddress;

/**
 * Runs in front of Spring Security's login (POST /auth/login): while LoginLimits says to wait, the password isn't
 * checked and the browser goes back to the login page with the minutes to wait. Not a bean, so it runs only in the
 * pages' filter chain (SecurityConfig).
 */
public class LoginLimitFilter extends OncePerRequestFilter {

    /**
     * The same test as Spring Security's login, which decodes the address: /auth/log%69n is a login too, so it must
     * wait here as well.
     */
    private static final RequestMatcher LOGIN = PathPatternRequestMatcher.withDefaults()
            .matcher(HttpMethod.POST, "/auth/login");

    private final LoginLimits limits;

    public LoginLimitFilter(LoginLimits limits) {
        this.limits = limits;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !LOGIN.matches(request);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        Duration wait = limits.waitFor(request.getParameter("email"), ClientAddress.of(request));
        if (wait.isZero()) {
            chain.doFilter(request, response);
            return;
        }
        response.sendRedirect(request.getContextPath() + "/auth/login?wait=" + Attempts.minutes(wait));
    }
}
