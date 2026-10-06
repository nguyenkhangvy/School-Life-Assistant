package vn.edu.hcmiu.sla.social.pages;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.flash;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicBoolean;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.User;
import vn.edu.hcmiu.sla.auth.UserRepository;
import vn.edu.hcmiu.sla.core.Flash;
import vn.edu.hcmiu.sla.social.model.SocialFriendship;
import vn.edu.hcmiu.sla.social.model.SocialFriendshipRepository;

/**
 * Two clicks on one request that land at the same moment get a message, never an error page
 * (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md, 8). The repository is wrapped to play the other
 * click: it hides a row once (the other click had just inserted it) or deletes the row right after this click read it
 * (the other click had just declined or cancelled it). Nothing here runs in a test transaction, so the accounts made
 * are deleted afterwards (their friendships go with them).
 */
@SpringBootTest
@AutoConfigureMockMvc
@Import(FriendsRaceTest.OtherClick.class)
class FriendsRaceTest {

    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 6, 7, 0);
    static final AtomicBoolean HIDE_NEXT_FIND = new AtomicBoolean();
    static final AtomicBoolean DELETE_AFTER_NEXT_FIND = new AtomicBoolean();
    static JdbcTemplate otherConnection;
    static TransactionTemplate ownTransaction; // the other click's: committed at once, whatever this click does

    @TestConfiguration
    static class OtherClick {

        @Bean
        static BeanPostProcessor otherClickOnFriendships() {
            return new BeanPostProcessor() {
                @Override
                public Object postProcessAfterInitialization(Object bean, String name) {
                    if (!(bean instanceof SocialFriendshipRepository real)) {
                        return bean;
                    }
                    return Proxy.newProxyInstance(SocialFriendshipRepository.class.getClassLoader(),
                            new Class<?>[] {SocialFriendshipRepository.class}, (proxy, method, args) -> {
                                boolean find = method.getName().equals("findBetween");
                                if (find && HIDE_NEXT_FIND.getAndSet(false)) {
                                    return Optional.empty();
                                }
                                Object result;
                                try {
                                    result = method.invoke(real, args);
                                } catch (InvocationTargetException error) {
                                    throw error.getCause();
                                }
                                if (find && DELETE_AFTER_NEXT_FIND.getAndSet(false)) {
                                    ((Optional<?>) result).ifPresent(row -> ownTransaction.executeWithoutResult(
                                            status -> otherConnection.update("DELETE FROM social_friendships WHERE id = ?",
                                                    ((SocialFriendship) row).getId())));
                                }
                                return result;
                            });
                }
            };
        }
    }

    @Autowired
    MockMvc mvc;

    @Autowired
    UserRepository users;

    @Autowired
    SocialFriendshipRepository friendships;

    @Autowired
    JdbcTemplate jdbc;

    @Autowired
    PlatformTransactionManager transactions;

    final List<Integer> made = new ArrayList<>();
    AppUser an;

    @BeforeEach
    void anAccount() {
        otherConnection = jdbc;
        ownTransaction = new TransactionTemplate(transactions);
        ownTransaction.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        an = AppUser.of(person("An"));
    }

    @AfterEach
    void cleanUp() {
        HIDE_NEXT_FIND.set(false);
        DELETE_AFTER_NEXT_FIND.set(false);
        users.deleteAllById(made);
    }

    User person(String name) {
        User user = users.save(new User("race-" + System.nanoTime() + "@example.com", name, "x", NOW));
        made.add(user.getId());
        return user;
    }

    ResultActions press(String path) throws Exception {
        return mvc.perform(post(path).with(user(an)).with(csrf()));
    }

    @Test
    void aDeclineThatMeetsTheOtherClicksDeclineStillSaysDeclined() throws Exception {
        User lan = person("Lan");
        friendships.save(SocialFriendship.request(lan.getId(), an.id(), NOW));
        DELETE_AFTER_NEXT_FIND.set(true);

        press("/social/friends/" + lan.getId() + "/decline")
                .andExpect(redirectedUrl("/social/friends"))
                .andExpect(flash().attribute("flashes", List.of(new Flash("message", "Declined Lan's request."))));

        assertThat(friendships.findBetween(an.id(), lan.getId())).isEmpty();
    }

    @Test
    void anAcceptThatMeetsTheSendersCancelSaysTheRequestIsGone() throws Exception {
        User lan = person("Lan");
        friendships.save(SocialFriendship.request(lan.getId(), an.id(), NOW));
        DELETE_AFTER_NEXT_FIND.set(true);

        press("/social/friends/" + lan.getId() + "/accept")
                .andExpect(redirectedUrl("/social/friends"))
                .andExpect(flash().attribute("flashes",
                        List.of(new Flash("error", "That request is no longer waiting."))));

        assertThat(friendships.findBetween(an.id(), lan.getId())).isEmpty();
    }

    @Test
    void anAddThatMeetsTheOtherClicksAddSendsOneRequest() throws Exception {
        User lan = person("Lan");
        friendships.save(SocialFriendship.request(an.id(), lan.getId(), NOW)); // the other click's row
        HIDE_NEXT_FIND.set(true); // this click doesn't see it, so its insert hits the unique key

        press("/social/friends/" + lan.getId() + "/add")
                .andExpect(redirectedUrl("/social/friends"))
                .andExpect(flash().attribute("flashes", List.of(new Flash("message", "Friend request sent to Lan."))));

        assertThat(friendships.findAllOf(an.id())).hasSize(1);
    }
}
