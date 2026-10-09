package vn.edu.hcmiu.sla.auth;

import java.time.Clock;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.validation.BindingResult;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import vn.edu.hcmiu.sla.core.Flash;

/** Profile and Password, for every role (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5.4 and 5.5). */
@Controller
@RequestMapping("/account")
public class AccountController {

    private static final ZoneOffset VIETNAM = ZoneOffset.ofHours(7); // as School's VietnamTime, which auth can't use
    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("dd/MM/yyyy");
    private static final DateTimeFormatter DATE_TIME = DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm");

    private final UserRepository users;
    private final Accounts accounts;
    private final PasswordEncoder passwords;
    private final Sessions sessions;
    private final Clock clock;

    public AccountController(UserRepository users, Accounts accounts, PasswordEncoder passwords, Sessions sessions,
            Clock clock) {
        this.users = users;
        this.accounts = accounts;
        this.passwords = passwords;
        this.sessions = sessions;
        this.clock = clock;
    }

    static String vietnam(LocalDateTime utc, DateTimeFormatter format) {
        return utc.atOffset(ZoneOffset.UTC).withOffsetSameInstant(VIETNAM).format(format);
    }

    /** Every page has just re-read the account (AccountCheck), so it is there. */
    private User account(AppUser user) {
        return users.findById(user.id()).orElseThrow();
    }

    private static String profilePage(User account, Model model) {
        model.addAttribute("role", account.getRole().label());
        model.addAttribute("memberSince", vietnam(account.getCreatedAt(), DATE));
        model.addAttribute("lastLogin",
                account.getLastLoginAt() == null ? "Never" : vietnam(account.getLastLoginAt(), DATE_TIME));
        return "auth/account";
    }

    @GetMapping
    String profile(@AuthenticationPrincipal AppUser user, Model model) {
        User account = account(user);
        ProfileForm form = new ProfileForm();
        form.setDisplayName(account.getDisplayName());
        form.setEmail(account.getEmail());
        model.addAttribute("form", form);
        return profilePage(account, model);
    }

    @PostMapping
    String saveProfile(@AuthenticationPrincipal AppUser user, @Valid @ModelAttribute("form") ProfileForm form,
            BindingResult errors, Model model, RedirectAttributes redirect) {
        User account = account(user);
        boolean newEmail = !form.getEmail().equals(account.getEmail());
        if (newEmail && !errors.hasFieldErrors("email") && users.existsByEmail(form.getEmail())) {
            errors.rejectValue("email", "taken", "This email is already registered.");
        }
        if (newEmail && form.getCurrentPassword().isEmpty()) {
            errors.rejectValue("currentPassword", "required", "Enter your current password to change your email.");
        } else if (newEmail && !passwords.matches(form.getCurrentPassword(), account.getPasswordHash())) {
            errors.rejectValue("currentPassword", "wrong", "Current password is incorrect.");
        }
        if (errors.hasErrors()) {
            return profilePage(account, model);
        }
        accounts.changeProfile(user.id(), form.getDisplayName(), form.getEmail(), LocalDateTime.now(clock));
        Flash.success(redirect, "Saved your profile.");
        return "redirect:/account";
    }

    @GetMapping("/password")
    String passwordPage(Model model) {
        model.addAttribute("form", new PasswordForm());
        return "auth/password";
    }

    @PostMapping("/password")
    String changePassword(@AuthenticationPrincipal AppUser user, @Valid @ModelAttribute("form") PasswordForm form,
            BindingResult errors, HttpServletRequest request, HttpServletResponse response,
            RedirectAttributes redirect) {
        User account = account(user);
        if (!passwords.matches(form.getCurrentPassword(), account.getPasswordHash())) {
            errors.rejectValue("currentPassword", "wrong", "Current password is incorrect.");
        } else if (!errors.hasFieldErrors("password") && passwords.matches(form.getPassword(), account.getPasswordHash())) {
            errors.rejectValue("password", "same", "Choose a password different from your current one.");
        }
        if (!form.getConfirm().isEmpty() && !form.getConfirm().equals(form.getPassword())) {
            errors.rejectValue("confirm", "mismatch", "Passwords don't match.");
        }
        if (errors.hasErrors()) {
            return "auth/password";
        }
        User changed = accounts.changePassword(user.id(), form.getPassword(), LocalDateTime.now(clock));
        sessions.logIn(AppUser.of(changed), request, response); // this session goes on; AccountCheck ends the others
        Flash.success(redirect, "Password changed.");
        return "redirect:/account";
    }
}
