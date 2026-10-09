package vn.edu.hcmiu.sla.auth;

import java.time.LocalDateTime;
import java.time.ZoneOffset;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;

import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.savedrequest.HttpSessionRequestCache;
import org.springframework.security.web.savedrequest.RequestCache;
import org.springframework.security.web.savedrequest.SavedRequest;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.validation.BindingResult;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;

/**
 * Register and the login page. Spring Security itself handles POST /auth/login and POST /auth/logout. A new account
 * is logged in and goes back to the page that asked for login, as login does: the Connect page, for a classmate who
 * had no account yet (spec 2026-10-04-connect-button-design.md, 4.3).
 */
@Controller
@RequestMapping("/auth")
public class AuthController {

    private final UserRepository users;
    private final PasswordEncoder passwords;
    private final Sessions sessions;
    /** Where Spring Security keeps the page that asked for login: its default, the one login reads. */
    private final RequestCache asked = new HttpSessionRequestCache();

    public AuthController(UserRepository users, PasswordEncoder passwords, Sessions sessions) {
        this.users = users;
        this.passwords = passwords;
        this.sessions = sessions;
    }

    @GetMapping("/login")
    String login() {
        return "auth/login";
    }

    @GetMapping("/register")
    String registerPage(Model model) {
        model.addAttribute("form", new RegisterForm());
        return "auth/register";
    }

    @PostMapping("/register")
    String register(@Valid @ModelAttribute("form") RegisterForm form, BindingResult errors,
                    HttpServletRequest request, HttpServletResponse response) {
        if (!form.getConfirm().isEmpty() && !form.getConfirm().equals(form.getPassword())) {
            errors.rejectValue("confirm", "mismatch", "Passwords don't match.");
        }
        if (!errors.hasFieldErrors("email") && users.existsByEmail(form.getEmail())) {
            errors.rejectValue("email", "taken", "This email is already registered.");
        }
        if (errors.hasErrors()) {
            return "auth/register";
        }
        LocalDateTime now = LocalDateTime.now(ZoneOffset.UTC);
        User account = new User(form.getEmail(), form.getDisplayName(), passwords.encode(form.getPassword()), now);
        account.loggedIn(now); // registering logs the new account in: its first login
        User user = users.save(account);
        sessions.logIn(AppUser.of(user), request, response);
        SavedRequest page = asked.getRequest(request, response);
        return "redirect:" + (page != null ? page.getRedirectUrl() : "/");
    }
}
