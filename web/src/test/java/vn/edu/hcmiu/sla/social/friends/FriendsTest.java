package vn.edu.hcmiu.sla.social.friends;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.sql.Connection;
import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.IntStream;

import javax.sql.DataSource;

import jakarta.persistence.EntityManager;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.domain.Page;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.social.SocialTestData;
import vn.edu.hcmiu.sla.social.friends.Friends.Friend;
import vn.edu.hcmiu.sla.social.friends.Friends.PersonRow;
import vn.edu.hcmiu.sla.social.friends.Friends.Request;
import vn.edu.hcmiu.sla.social.friends.Friends.Result;
import vn.edu.hcmiu.sla.social.friends.Friends.Standing;
import vn.edu.hcmiu.sla.social.model.SocialFriendshipRepository;

/** Find people and friend requests (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md, 4.2 and 6.4). */
@SpringBootTest
@Transactional
class FriendsTest {

    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 6, 7, 0);

    @Autowired
    EntityManager db;

    @Autowired
    Friends friends;

    @Autowired
    SocialFriendshipRepository friendships;

    @Autowired
    DataSource dataSource;

    SocialTestData data;
    AppUser an;

    @BeforeEach
    void anAccount() {
        data = new SocialTestData(db);
        an = data.person("An Nguyen");
    }

    static List<String> names(Page<PersonRow> page) {
        return page.getContent().stream().map(PersonRow::name).toList();
    }

    static Result ok(String message) {
        return new Result(true, message);
    }

    static Result error(String message) {
        return new Result(false, message);
    }

    // ---- Find people ---------------------------------------------------------------------

    @Test
    void searchMatchesAnyPartOfTheNameIgnoringCaseSortedByName() {
        data.person("Trang Le");
        data.person("Thu TRANG");
        data.person("Binh");

        assertThat(names(friends.search(an.id(), "trang", 1))).containsExactly("Thu TRANG", "Trang Le");
    }

    @Test
    void searchNeverListsTheOneSearching() {
        AppUser lan = data.person("Lan Self");
        data.person("Lan Other");

        assertThat(names(friends.search(lan.id(), "lan", 1))).containsExactly("Lan Other");
    }

    @Test
    void searchShowsWhereEachPersonStands() {
        AppUser asked = data.person("Lan Asked");
        AppUser asker = data.person("Lan Asker");
        AppUser friend = data.person("Lan Friend");
        data.person("Lan Stranger");
        data.request(an, asked, NOW);
        data.request(asker, an, NOW);
        data.friends(an, friend);

        assertThat(friends.search(an.id(), "lan", 1).getContent())
                .extracting(PersonRow::name, PersonRow::standing)
                .containsExactly(tuple("Lan Asked", Standing.SENT), tuple("Lan Asker", Standing.RECEIVED),
                        tuple("Lan Friend", Standing.FRIENDS), tuple("Lan Stranger", Standing.NONE));
    }

    @Test
    void likesOwnCharactersAreMatchedLiterally() {
        data.person("Lan Anh");
        data.person("Lan_Anh");
        data.person("100% Lan");

        assertThat(names(friends.search(an.id(), "_a", 1))).containsExactly("Lan_Anh");
        assertThat(names(friends.search(an.id(), "% l", 1))).containsExactly("100% Lan");
        assertThat(names(friends.search(an.id(), "%%", 1))).isEmpty();
        assertThat(names(friends.search(an.id(), "!%", 1))).isEmpty();
    }

    @Test
    void theContainsPatternEscapesLikesCharacters() {
        assertThat(Friends.containsPattern("A_b%c!")).isEqualTo("%a!_b!%c!!%");
    }

    @Test
    void twentyAPageAndAPagePastTheEndShowsTheLast() {
        IntStream.rangeClosed(1, 25).forEach(n -> data.person(String.format("Lan %02d", n)));

        Page<PersonRow> first = friends.search(an.id(), "lan", 1);
        assertThat(first.getContent()).hasSize(20);
        assertThat(first.getTotalElements()).isEqualTo(25);
        assertThat(names(friends.search(an.id(), "lan", 2)))
                .containsExactly("Lan 21", "Lan 22", "Lan 23", "Lan 24", "Lan 25");

        Page<PersonRow> past = friends.search(an.id(), "lan", 9);
        assertThat(past.getNumber()).isEqualTo(1); // the second page, counted from 0
        assertThat(past.getContent()).hasSize(5);
    }

    @Test
    void accentsAreIgnoredOnMySql() throws Exception {
        try (Connection connection = dataSource.getConnection()) {
            assumeTrue("MySQL".equals(connection.getMetaData().getDatabaseProductName()),
                    "only MySQL's collation (utf8mb4_0900_ai_ci) ignores accents; GitHub's checks run this on MySQL");
        }
        data.person("Vỹ Nguyễn");

        assertThat(names(friends.search(an.id(), "vy nguyen", 1))).containsExactly("Vỹ Nguyễn");
    }

    // ---- The buttons -------------------------------------------------------------------

    @Test
    void addingSendsOneRequest() {
        AppUser lan = data.person("Lan");

        assertThat(friends.add(an.id(), lan.id(), NOW)).contains(ok("Friend request sent to Lan."));
        assertThat(friends.add(an.id(), lan.id(), NOW)).contains(ok("Friend request sent to Lan."));

        assertThat(friendships.findAllOf(an.id())).singleElement().satisfies(request -> {
            assertThat(request.isPending()).isTrue();
            assertThat(request.isSentBy(an.id())).isTrue();
            assertThat(request.getCreatedAt()).isEqualTo(NOW);
        });
    }

    @Test
    void addingSomeoneWhoAlreadyAskedYouMakesYouFriends() {
        AppUser lan = data.person("Lan");
        data.request(lan, an, NOW.minusDays(1));

        assertThat(friends.add(an.id(), lan.id(), NOW)).contains(ok("You and Lan are now friends."));
        assertThat(friends.friendsOf(an.id())).extracting(Friend::name).containsExactly("Lan");
    }

    @Test
    void addingAFriendAgainSaysSo() {
        AppUser lan = data.person("Lan");
        data.friends(an, lan);

        assertThat(friends.add(an.id(), lan.id(), NOW)).contains(ok("You and Lan are already friends."));
    }

    @Test
    void acceptingMakesFriendsOnceAndRefusesWhenNothingWaits() {
        AppUser lan = data.person("Lan");
        AppUser binh = data.person("Binh");
        data.request(lan, an, NOW.minusDays(1));
        data.request(an, binh, NOW.minusDays(1));

        assertThat(friends.accept(an.id(), lan.id(), NOW)).contains(ok("You and Lan are now friends."));
        assertThat(friendships.findBetween(an.id(), lan.id()).orElseThrow().getAcceptedAt()).isEqualTo(NOW);
        assertThat(friends.accept(an.id(), lan.id(), NOW)).contains(ok("You and Lan are already friends."));

        assertThat(friends.accept(an.id(), binh.id(), NOW)).contains(error("That request is no longer waiting."));
        assertThat(friendships.findBetween(an.id(), binh.id()).orElseThrow().isPending()).isTrue(); // unchanged
        AppUser cuong = data.person("Cuong");
        assertThat(friends.accept(an.id(), cuong.id(), NOW)).contains(error("That request is no longer waiting."));
    }

    @Test
    void decliningRemovesTheRequest() {
        AppUser lan = data.person("Lan");
        data.request(lan, an, NOW);

        assertThat(friends.decline(an.id(), lan.id(), NOW)).contains(ok("Declined Lan's request."));
        assertThat(friendships.findBetween(an.id(), lan.id())).isEmpty();
        assertThat(friends.decline(an.id(), lan.id(), NOW)).contains(ok("Declined Lan's request.")); // a double click

        AppUser friend = data.person("Binh");
        data.friends(friend, an);
        assertThat(friends.decline(an.id(), friend.id(), NOW)).contains(error("You and Binh are already friends."));
        AppUser asked = data.person("Cuong");
        data.request(an, asked, NOW);
        assertThat(friends.decline(an.id(), asked.id(), NOW)).contains(error("That request is no longer waiting."));
    }

    @Test
    void cancellingRemovesYourRequestButNotAFriendship() {
        AppUser lan = data.person("Lan");
        data.request(an, lan, NOW);

        assertThat(friends.cancel(an.id(), lan.id(), NOW)).contains(ok("Cancelled your request to Lan."));
        assertThat(friendships.findBetween(an.id(), lan.id())).isEmpty();
        assertThat(friends.cancel(an.id(), lan.id(), NOW)).contains(ok("Cancelled your request to Lan."));

        AppUser binh = data.person("Binh");
        data.friends(an, binh);
        assertThat(friends.cancel(an.id(), binh.id(), NOW)).contains(error("Binh already accepted: you're friends now."));
        AppUser asker = data.person("Cuong");
        data.request(asker, an, NOW);
        assertThat(friends.cancel(an.id(), asker.id(), NOW)).contains(error("That request is no longer waiting."));
    }

    @Test
    void removingEndsAFriendshipButNotARequest() {
        AppUser lan = data.person("Lan");
        data.friends(lan, an);

        assertThat(friends.remove(an.id(), lan.id(), NOW)).contains(ok("Removed Lan from your friends."));
        assertThat(friendships.findBetween(an.id(), lan.id())).isEmpty();
        assertThat(friends.remove(an.id(), lan.id(), NOW)).contains(ok("Removed Lan from your friends."));

        AppUser binh = data.person("Binh");
        data.request(binh, an, NOW);
        assertThat(friends.remove(an.id(), binh.id(), NOW)).contains(error("You and Binh aren't friends yet."));
    }

    @Test
    void anUnknownPersonOrYourselfGivesNothing() {
        assertThat(friends.add(an.id(), 999_999, NOW)).isEmpty();
        assertThat(friends.add(an.id(), an.id(), NOW)).isEmpty();
        assertThat(friends.accept(an.id(), an.id(), NOW)).isEmpty();
        assertThat(friends.remove(an.id(), 999_999, NOW)).isEmpty();
        assertThat(friendships.findAllOf(an.id())).isEmpty();
    }

    // ---- The lists and the count --------------------------------------------------------

    @Test
    void requestsAreNewestFirstAndFriendsByName() {
        AppUser lan = data.person("Lan");
        AppUser binh = data.person("Binh");
        AppUser cuong = data.person("Cuong");
        data.request(lan, an, NOW.minusDays(2));
        data.request(binh, an, NOW.minusDays(1));
        data.request(an, cuong, NOW);
        data.friends(an, data.person("dung"));
        data.friends(data.person("Anh"), an);
        data.friends(an, data.person("binh tran"));

        assertThat(friends.requestsFor(an.id())).extracting(Request::name, Request::sentAt)
                .containsExactly(tuple("Binh", NOW.minusDays(1)), tuple("Lan", NOW.minusDays(2)));
        assertThat(friends.requestsSentBy(an.id())).extracting(Request::name).containsExactly("Cuong");
        assertThat(friends.friendsOf(an.id())).extracting(Friend::name).containsExactly("Anh", "binh tran", "dung");
    }

    @Test
    void theCountIsRequestsWaitingForYou() {
        AppUser cuong = data.person("Cuong");
        data.request(data.person("Lan"), an, NOW);
        data.request(data.person("Binh"), an, NOW);
        data.request(an, cuong, NOW);
        data.friends(an, data.person("Dung"));

        assertThat(friends.countRequestsFor(an.id())).isEqualTo(2);
        assertThat(friends.countRequestsFor(cuong.id())).isEqualTo(1);
    }
}
