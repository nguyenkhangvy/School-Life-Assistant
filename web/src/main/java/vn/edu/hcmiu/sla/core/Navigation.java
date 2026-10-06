package vn.edu.hcmiu.sla.core;

import java.util.List;
import java.util.Map;
import java.util.function.IntSupplier;
import java.util.stream.Collectors;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ModelAttribute;

import vn.edu.hcmiu.sla.auth.AppUser;

/** Gives every page the menu: the modules in a fixed order, with a link for each one that exists, and its count. */
@ControllerAdvice
public class Navigation {

    static final List<String> MODULES = List.of("School", "Groups", "Friends");

    /**
     * One menu entry; path is null while the module doesn't exist yet. The count is worked out only when a page shows
     * the menu, so a request that shows none (the calendar's feed, a redirect) runs no count query.
     */
    public record NavItem(String label, String path, IntSupplier counter) {

        /** The number after the label for the logged-in student; 0 shows nothing. */
        public int count() {
            return counter == null ? 0 : counter.getAsInt();
        }
    }

    private final Map<String, String> paths;
    private final Map<String, NavCount> counts;

    public Navigation(List<NavModule> modules, List<NavCount> counts) {
        this.paths = modules.stream().collect(Collectors.toMap(NavModule::label, NavModule::path, (a, b) -> a));
        this.counts = counts.stream().collect(Collectors.toMap(NavCount::label, count -> count, (a, b) -> a));
    }

    /** user is null on the login and register pages. */
    @ModelAttribute("navItems")
    public List<NavItem> navItems(@AuthenticationPrincipal AppUser user) {
        return MODULES.stream().map(label -> {
            String path = paths.get(label);
            NavCount count = counts.get(label);
            IntSupplier counter = user == null || path == null || count == null ? null : () -> count.of(user.id());
            return new NavItem(label, path, counter);
        }).toList();
    }
}
