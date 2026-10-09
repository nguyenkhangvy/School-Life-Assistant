package vn.edu.hcmiu.sla.core;

import java.util.List;
import java.util.Map;
import java.util.function.IntSupplier;
import java.util.stream.Collectors;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.TransactionException;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ModelAttribute;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;

/**
 * Gives every page the menu: the logged-in role's modules in a fixed order, with a link for each one that exists, and
 * its count.
 */
@ControllerAdvice
public class Navigation {

    /** Each role's menu (docs/superpowers/specs/2026-10-06-site-roles-design.md, 4.3). */
    static final Map<Role, List<String>> MODULES = Map.of(
            Role.STUDENT, List.of("School", "Groups", "Friends"),
            Role.AUDITOR, List.of("Audit log", "Statistics"),
            Role.ADMIN, List.of("Users", "Audit log", "Statistics"));
    private static final Logger LOG = LoggerFactory.getLogger(Navigation.class);

    /**
     * One menu entry; path is null while the module doesn't exist yet. The count is worked out only when a page shows
     * the menu, so a request that shows none (the calendar's feed, a redirect) runs no count query.
     */
    public record NavItem(String label, String path, IntSupplier counter) {

        /**
         * The number after the label for the logged-in student; 0 shows nothing. A count the database can't give (it is
         * down, say, while the error page is shown) is 0 too, so the page still opens.
         */
        public int count() {
            if (counter == null) {
                return 0;
            }
            try {
                return counter.getAsInt();
            } catch (DataAccessException | TransactionException error) {
                LOG.warn("The menu count for {} couldn't be read: {}", label, error.getMessage());
                return 0;
            }
        }
    }

    private final Map<String, String> paths;
    private final Map<String, NavCount> counts;

    public Navigation(List<NavModule> modules, List<NavCount> counts) {
        this.paths = modules.stream().collect(Collectors.toMap(NavModule::label, NavModule::path, (a, b) -> a));
        this.counts = counts.stream().collect(Collectors.toMap(NavCount::label, count -> count, (a, b) -> a));
    }

    /** user is null on the login and register pages, which show no menu. */
    @ModelAttribute("navItems")
    public List<NavItem> navItems(@AuthenticationPrincipal AppUser user) {
        if (user == null) {
            return List.of();
        }
        return MODULES.get(user.role()).stream().map(label -> {
            String path = paths.get(label);
            NavCount count = counts.get(label);
            IntSupplier counter = path == null || count == null ? null : () -> count.of(user.id());
            return new NavItem(label, path, counter);
        }).toList();
    }
}
