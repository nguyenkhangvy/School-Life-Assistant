package vn.edu.hcmiu.sla.core;

import java.util.Map;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.DisabledException;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.crypto.argon2.Argon2PasswordEncoder;
import org.springframework.security.crypto.password.DelegatingPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.access.intercept.AuthorizationFilter;
import org.springframework.security.web.authentication.AuthenticationFailureHandler;
import org.springframework.security.web.authentication.ExceptionMappingAuthenticationFailureHandler;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter.ReferrerPolicy;

import vn.edu.hcmiu.sla.auth.AccountCheck;
import vn.edu.hcmiu.sla.auth.Accounts;
import vn.edu.hcmiu.sla.auth.AppUserDetailsService;
import vn.edu.hcmiu.sla.auth.LoggedIn;
import vn.edu.hcmiu.sla.auth.LoginLimitFilter;
import vn.edu.hcmiu.sla.auth.LoginLimits;
import vn.edu.hcmiu.sla.auth.Role;
import vn.edu.hcmiu.sla.auth.UserRepository;
import vn.edu.hcmiu.sla.auth.WerkzeugPasswordEncoder;

/**
 * Who may open what (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.2): the lists below, read top to
 * bottom; AccessListTest checks that every page is in one. Every form carries a CSRF token. Method security is on, so
 * an action can check the role a second time with @PreAuthorize.
 */
@Configuration
@EnableMethodSecurity
public class SecurityConfig {

    static final String[] ANYONE = {"/auth/login", "/auth/register", "/css/**", "/js/**", "/error"};
    static final String[] STUDENTS = {"/school/**", "/social/**"};
    static final String[] ADMINS = {"/admin/users/**"};
    static final String[] STAFF = {"/admin/audit-log/**", "/admin/statistics/**"};
    static final String[] EVERY_ROLE = {"/", "/account/**", "/auth/logout"};

    /** The Content-Security-Policy (security hardening spec, 5). */
    static final String CONTENT_SECURITY_POLICY = "default-src 'self'; "
            + "script-src 'self' https://cdn.jsdelivr.net/npm/fullcalendar@6.1.21/; "
            + "style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data:; connect-src 'self'; "
            + "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self' http://127.0.0.1:*";
    static final String PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()";

    @Bean
    SecurityFilterChain pages(HttpSecurity http, LoggedIn loggedIn, Refusals refusals, UserRepository users,
            SecurityContextRepository logins, LoginLimits limits) throws Exception {
        http
                .authorizeHttpRequests(pages -> pages
                        .requestMatchers(ANYONE).permitAll()
                        .requestMatchers(STUDENTS).hasRole(Role.STUDENT.name())
                        .requestMatchers(ADMINS).hasRole(Role.ADMIN.name())
                        .requestMatchers(STAFF).hasAnyRole(Role.AUDITOR.name(), Role.ADMIN.name())
                        .requestMatchers(EVERY_ROLE).authenticated()
                        .anyRequest().authenticated()) // a mistyped address: "Page not found", for any role
                .addFilterBefore(new AccountCheck(users, logins), AuthorizationFilter.class)
                .addFilterBefore(new LoginLimitFilter(limits), UsernamePasswordAuthenticationFilter.class)
                .exceptionHandling(refused -> refused.accessDeniedHandler(refusals))
                .formLogin(login -> login
                        .loginPage("/auth/login")
                        .usernameParameter("email")
                        .passwordParameter("password")
                        .successHandler(loggedIn) // back to the page that asked for login, else home
                        .failureHandler(loginFailed(limits))
                        .permitAll())
                .logout(logout -> logout
                        .logoutUrl("/auth/logout")
                        .logoutSuccessUrl("/auth/login"));
        securityHeaders(http);
        return http.build();
    }

    /**
     * What both filter chains add (security hardening spec, 5): Content-Security-Policy, Referrer-Policy and
     * Permissions-Policy, on top of Spring Security's HSTS, nosniff, X-Frame-Options and no-store. Scripts come only
     * from the site and FullCalendar's folder on jsDelivr; form-action allows the redirect to the laptop app on this
     * computer that ends the Connect page; FullCalendar adds its own <style>, hence 'unsafe-inline' for styles only, and
     * draws its arrows with a data: font.
     */
    public static void securityHeaders(HttpSecurity http) throws Exception {
        http.headers(headers -> headers
                .contentSecurityPolicy(csp -> csp.policyDirectives(CONTENT_SECURITY_POLICY))
                .referrerPolicy(referrer -> referrer.policy(ReferrerPolicy.SAME_ORIGIN))
                .permissionsPolicyHeader(permissions -> permissions.policy(PERMISSIONS_POLICY)));
    }

    /**
     * A wrong password or an unknown email: counted (LoginLimits), then ?error. The right password for a deactivated
     * account: ?deactivated, not counted (it isn't a guess).
     */
    static AuthenticationFailureHandler loginFailed(LoginLimits limits) {
        ExceptionMappingAuthenticationFailureHandler pages = new ExceptionMappingAuthenticationFailureHandler();
        pages.setDefaultFailureUrl("/auth/login?error");
        pages.setExceptionMappings(Map.of(DisabledException.class.getName(), "/auth/login?deactivated"));
        return (request, response, failure) -> {
            if (failure instanceof BadCredentialsException) {
                limits.failed(request.getParameter("email"), ClientAddress.of(request));
            }
            pages.onAuthenticationFailure(request, response, failure);
        };
    }

    /**
     * Checks the email and password. Spring Security normally refuses a disabled account before it looks at the
     * password, which would tell anyone which emails have accounts; here only the right password learns that the
     * account is deactivated (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5.1). The site's only
     * AuthenticationProvider, so Spring Security uses it for every login. Spring re-hashes an old password at login
     * through Accounts.rehash.
     */
    @Bean
    DaoAuthenticationProvider passwordLogin(AppUserDetailsService users, PasswordEncoder passwords, Accounts accounts) {
        DaoAuthenticationProvider provider = new DaoAuthenticationProvider(users);
        provider.setPasswordEncoder(passwords);
        provider.setUserDetailsPasswordService(accounts::rehash); // an old hash becomes Argon2id at login
        provider.setPreAuthenticationChecks(account -> {
        });
        provider.setPostAuthenticationChecks(account -> {
            if (!account.isEnabled()) {
                throw new DisabledException("This account has been deactivated");
            }
        });
        return provider;
    }

    /**
     * New hashes are Argon2id with OWASP's settings (security hardening spec, 4): {argon2}$argon2id$…. A hash with no
     * {id} prefix is the old scrypt (Werkzeug) format, which WerkzeugPasswordEncoder still checks; the login provider
     * re-hashes it at the next login (Accounts.rehash).
     */
    @Bean
    PasswordEncoder passwordEncoder() {
        DelegatingPasswordEncoder passwords = new DelegatingPasswordEncoder("argon2",
                Map.of("argon2", new Argon2PasswordEncoder(16, 32, 1, 19456, 2)));
        passwords.setDefaultPasswordEncoderForMatches(new WerkzeugPasswordEncoder());
        return passwords;
    }

    /** Where a login is kept between requests; the register page uses it to log the new account in. */
    @Bean
    SecurityContextRepository securityContextRepository() {
        return new HttpSessionSecurityContextRepository();
    }
}
