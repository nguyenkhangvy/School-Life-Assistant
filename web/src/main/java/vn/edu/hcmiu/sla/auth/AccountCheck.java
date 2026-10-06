package vn.edu.hcmiu.sla.auth;

import java.io.IOException;
import java.util.Optional;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.logout.SecurityContextLogoutHandler;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Re-reads the logged-in account on every page (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.4), so a
 * change reaches a session that is already open on its next click: a deactivated or deleted account, or one whose
 * password changed somewhere else, is logged out; a new role, name or email goes into the session, so the menu and the
 * access list follow at once. One lookup by id. Static files are skipped, and so is the error page (OncePerRequestFilter
 * leaves out error dispatches). SecurityConfig places it before the access list; it is not a bean, so it runs only
 * there.
 */
public class AccountCheck extends OncePerRequestFilter {

    private final UserRepository users;
    private final SecurityContextRepository logins;
    private final SecurityContextLogoutHandler logout = new SecurityContextLogoutHandler();

    public AccountCheck(UserRepository users, SecurityContextRepository logins) {
        this.users = users;
        this.logins = logins;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI().substring(request.getContextPath().length());
        return path.startsWith("/css/") || path.startsWith("/js/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        Authentication login = SecurityContextHolder.getContext().getAuthentication();
        if (login != null && login.getPrincipal() instanceof AppUser user) {
            Optional<User> account = users.findById(user.id());
            String ended = account.isEmpty() ? ""
                    : !account.get().isActive() ? "?deactivated"
                    : !account.get().getPasswordHash().equals(user.passwordHash()) ? "?changed"
                    : null;
            if (ended != null) {
                logout.logout(request, response, login);
                response.sendRedirect(request.getContextPath() + "/auth/login" + ended);
                return;
            }
            AppUser now = AppUser.of(account.get());
            if (!now.equals(user)) {
                SecurityContext context = SecurityContextHolder.createEmptyContext();
                context.setAuthentication(UsernamePasswordAuthenticationToken.authenticated(now, null,
                        now.getAuthorities()));
                SecurityContextHolder.setContext(context);
                logins.saveContext(context, request, response);
            }
        }
        chain.doFilter(request, response);
    }
}
