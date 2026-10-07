package vn.edu.hcmiu.sla.auth;

import java.io.IOException;
import java.time.Duration;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.web.filter.OncePerRequestFilter;

import vn.edu.hcmiu.sla.core.Attempts;
import vn.edu.hcmiu.sla.core.ClientAddress;

/**
 * Runs in front of Spring Security's login (POST /auth/login): while LoginLimits says to wait, the password isn't
 * checked and the browser goes back to the login page with the minutes to wait. Not a bean, so it runs only in the
 * pages' filter chain (SecurityConfig).
 */
public class LoginLimitFilter extends OncePerRequestFilter {

    private final LoginLimits limits;

    public LoginLimitFilter(LoginLimits limits) {
        this.limits = limits;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI().substring(request.getContextPath().length());
        return !("POST".equals(request.getMethod()) && path.equals("/auth/login"));
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
