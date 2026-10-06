package vn.edu.hcmiu.sla.core;

import java.util.Map;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.DisabledException;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AuthenticationFailureHandler;
import org.springframework.security.web.authentication.ExceptionMappingAuthenticationFailureHandler;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;

import vn.edu.hcmiu.sla.auth.AppUserDetailsService;
import vn.edu.hcmiu.sla.auth.LoggedIn;
import vn.edu.hcmiu.sla.auth.WerkzeugPasswordEncoder;

/** Every page needs login except login, register and static files. Every form carries a CSRF token. */
@Configuration
public class SecurityConfig {

    @Bean
    SecurityFilterChain pages(HttpSecurity http, LoggedIn loggedIn) throws Exception {
        http
                .authorizeHttpRequests(pages -> pages
                        .requestMatchers("/auth/login", "/auth/register", "/css/**", "/js/**", "/error").permitAll()
                        .anyRequest().authenticated())
                .formLogin(login -> login
                        .loginPage("/auth/login")
                        .usernameParameter("email")
                        .passwordParameter("password")
                        .successHandler(loggedIn) // back to the page that asked for login, else home
                        .failureHandler(loginFailed())
                        .permitAll())
                .logout(logout -> logout
                        .logoutUrl("/auth/logout")
                        .logoutSuccessUrl("/auth/login"));
        return http.build();
    }

    /** A wrong password or an unknown email: ?error. The right password for a deactivated account: ?deactivated. */
    static AuthenticationFailureHandler loginFailed() {
        ExceptionMappingAuthenticationFailureHandler failed = new ExceptionMappingAuthenticationFailureHandler();
        failed.setDefaultFailureUrl("/auth/login?error");
        failed.setExceptionMappings(Map.of(DisabledException.class.getName(), "/auth/login?deactivated"));
        return failed;
    }

    /**
     * Checks the email and password. Spring Security normally refuses a disabled account before it looks at the
     * password, which would tell anyone which emails have accounts; here only the right password learns that the
     * account is deactivated (docs/superpowers/specs/2026-10-06-site-roles-design.md, 5.1). The site's only
     * AuthenticationProvider, so Spring Security uses it for every login.
     */
    @Bean
    DaoAuthenticationProvider passwordLogin(AppUserDetailsService accounts, PasswordEncoder passwords) {
        DaoAuthenticationProvider provider = new DaoAuthenticationProvider(accounts);
        provider.setPasswordEncoder(passwords);
        provider.setPreAuthenticationChecks(account -> {
        });
        provider.setPostAuthenticationChecks(account -> {
            if (!account.isEnabled()) {
                throw new DisabledException("This account has been deactivated");
            }
        });
        return provider;
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new WerkzeugPasswordEncoder();
    }

    /** Where a login is kept between requests; the register page uses it to log the new account in. */
    @Bean
    SecurityContextRepository securityContextRepository() {
        return new HttpSessionSecurityContextRepository();
    }
}
