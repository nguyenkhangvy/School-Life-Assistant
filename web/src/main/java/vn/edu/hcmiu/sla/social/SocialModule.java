package vn.edu.hcmiu.sla.social;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import vn.edu.hcmiu.sla.core.NavCount;
import vn.edu.hcmiu.sla.core.NavModule;
import vn.edu.hcmiu.sla.social.friends.Friends;

/**
 * Puts Friends in the menu and on the dashboard, with the number of friend requests waiting
 * (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md, 4.1). Groups registers here in stage 2; until then
 * the menu shows it as coming soon.
 */
@Configuration
class SocialModule {

    @Bean
    NavModule friendsMenu() {
        return new NavModule("Friends", "/social/friends");
    }

    @Bean
    NavCount friendsCount(Friends friends) {
        return new NavCount("Friends", friends::countRequestsFor);
    }
}
