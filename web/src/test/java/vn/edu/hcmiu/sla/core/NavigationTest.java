package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.transaction.CannotCreateTransactionException;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;
import vn.edu.hcmiu.sla.core.Navigation.NavItem;

class NavigationTest {

    static final AppUser AN = new AppUser(7, "an@example.com", "An", "x", Role.STUDENT, true);
    static final NavModule FRIENDS = new NavModule("Friends", "/social/friends");

    @Test
    void everyModuleIsListedAndComingSoonUntilItRegisters() {
        assertThat(new Navigation(List.of(), List.of()).navItems(AN))
                .extracting(NavItem::label, NavItem::path)
                .containsExactly(tuple("School", null), tuple("Groups", null), tuple("Friends", null));
    }

    @Test
    void aRegisteredModuleGetsItsLink() {
        assertThat(new Navigation(List.of(new NavModule("School", "/school")), List.of()).navItems(AN))
                .extracting(NavItem::label, NavItem::path)
                .containsExactly(tuple("School", "/school"), tuple("Groups", null), tuple("Friends", null));
    }

    @Test
    void aModulesCountIsTheLoggedInStudents() {
        Navigation navigation = new Navigation(List.of(FRIENDS),
                List.of(new NavCount("Friends", userId -> userId == 7 ? 2 : 5)));

        assertThat(navigation.navItems(AN)).extracting(NavItem::count).containsExactly(0, 0, 2);
    }

    @Test
    void nothingIsCountedWhenLoggedOutOrForAModuleNotBuiltYet() {
        NavCount two = new NavCount("Friends", userId -> 2);

        assertThat(new Navigation(List.of(FRIENDS), List.of(two)).navItems(null))
                .extracting(NavItem::count).containsExactly(0, 0, 0);
        assertThat(new Navigation(List.of(), List.of(two)).navItems(AN))
                .extracting(NavItem::count).containsExactly(0, 0, 0);
    }

    @Test
    void aCountThatCantBeReadShowsNothingSoThePageStillOpens() {
        Navigation navigation = new Navigation(List.of(FRIENDS), List.of(new NavCount("Friends", userId -> {
            throw new DataAccessResourceFailureException("The database is down");
        })));

        assertThat(navigation.navItems(AN).get(2).count()).isZero(); // e.g. the error page, while the database is down

        Navigation noConnection = new Navigation(List.of(FRIENDS), List.of(new NavCount("Friends", userId -> {
            throw new CannotCreateTransactionException("No connection"); // what @Transactional gives when it is down
        })));
        assertThat(noConnection.navItems(AN).get(2).count()).isZero();
    }

    @Test
    void aCountIsWorkedOutOnlyWhenThePageShowsIt() {
        AtomicInteger asked = new AtomicInteger();
        Navigation navigation = new Navigation(List.of(FRIENDS),
                List.of(new NavCount("Friends", userId -> asked.incrementAndGet())));

        List<NavItem> items = navigation.navItems(AN);
        assertThat(asked).hasValue(0); // an API call that shows no menu costs nothing

        items.get(2).count();
        assertThat(asked).hasValue(1);
    }
}
