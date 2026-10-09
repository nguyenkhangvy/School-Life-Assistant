package vn.edu.hcmiu.sla.core;

import java.io.IOException;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.security.web.csrf.CsrfException;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ModelAttribute;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;

/**
 * Why a page was refused (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.5). Spring Security calls
 * {@link #handle} for a role the access list doesn't allow and for a form without its security code (CSRF): the reason
 * goes on the request, then the server shows the error page (403), which explains it through the "refusal" model
 * attribute.
 */
@ControllerAdvice
public class Refusals implements AccessDeniedHandler {

    public static final String REASON = "sla.refusal";
    public static final String ROLE = "role";
    public static final String CONNECT = "connect";
    public static final String FORM = "form";

    static final String CONNECT_PAGE = "/school/devices/connect";
    static final String CANT_OPEN = "You can't open this page";

    /** What the 403 page says; offerLogOut adds a Log out button. */
    public record Refusal(String title, String text, boolean offerLogOut) {
    }

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, AccessDeniedException denied)
            throws IOException {
        String path = request.getRequestURI().substring(request.getContextPath().length());
        request.setAttribute(REASON, denied instanceof CsrfException ? FORM
                : path.equals(CONNECT_PAGE) || path.startsWith(CONNECT_PAGE + "/") ? CONNECT
                : ROLE);
        response.sendError(HttpServletResponse.SC_FORBIDDEN);
    }

    /** null on every page but a refused one. */
    @ModelAttribute("refusal")
    public Refusal refusal(HttpServletRequest request, @AuthenticationPrincipal AppUser user) {
        Object reason = request.getAttribute(REASON);
        if (reason == null) {
            return null;
        }
        if (FORM.equals(reason)) {
            return new Refusal("This form expired", "Go back, reload the page and try again.", false);
        }
        if (CONNECT.equals(reason)) {
            return new Refusal(CANT_OPEN,
                    "Only student accounts can connect a laptop. Log out and log in with your student account.", true);
        }
        return new Refusal(CANT_OPEN, user == null ? null : canOpen(user.role()), false);
    }

    static String canOpen(Role role) {
        return switch (role) {
            case STUDENT -> "Your account is a student account: it can open School, Groups and Friends.";
            case AUDITOR -> "Your account is an Auditor account: it can open the Audit log and Statistics.";
            case ADMIN -> "Your account is an Admin account: it can open Users, the Audit log and Statistics.";
        };
    }
}
