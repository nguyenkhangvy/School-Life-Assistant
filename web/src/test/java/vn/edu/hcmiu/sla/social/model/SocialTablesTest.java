package vn.edu.hcmiu.sla.social.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.Timestamp;
import java.time.LocalDateTime;

import jakarta.persistence.EntityManager;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.auth.User;
import vn.edu.hcmiu.sla.auth.UserRepository;

/** The Social classes fit their tables (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md, 3.1). */
@SpringBootTest
@Transactional
class SocialTablesTest {

    static final LocalDateTime OCT_6 = LocalDateTime.of(2026, 10, 6, 1, 0);

    @Autowired
    EntityManager db;

    @Autowired
    UserRepository users;

    @Autowired
    SocialFriendshipRepository friendships;

    @Autowired
    JdbcTemplate jdbc;

    Integer an;
    Integer binh;
    Integer cuong;

    @BeforeEach
    void threeAccounts() {
        an = users.save(new User("an@example.com", "An", "x", OCT_6)).getId();
        binh = users.save(new User("binh@example.com", "Binh", "x", OCT_6)).getId();
        cuong = users.save(new User("cuong@example.com", "Cuong", "x", OCT_6)).getId();
    }

    @Test
    void aRequestIsKeptSmallerIdFirstWithItsSender() {
        friendships.save(SocialFriendship.request(binh, an, OCT_6)); // binh's id is the larger
        db.flush();
        db.clear();

        SocialFriendship again = friendships.findBetween(an, binh).orElseThrow();

        assertThat(again.getUserLowId()).isEqualTo(an);
        assertThat(again.getUserHighId()).isEqualTo(binh);
        assertThat(again.isSentBy(binh)).isTrue();
        assertThat(again.isSentBy(an)).isFalse();
        assertThat(again.isPending()).isTrue();
        assertThat(again.other(an)).isEqualTo(binh);
        assertThat(again.other(binh)).isEqualTo(an);
        assertThat(again.getCreatedAt()).isEqualTo(OCT_6);
        assertThat(again.getAcceptedAt()).isNull();
        assertThat(friendships.findBetween(binh, an)).isPresent(); // either order finds it
    }

    @Test
    void acceptingKeepsWhen() {
        SocialFriendship request = friendships.save(SocialFriendship.request(an, binh, OCT_6));
        request.accept(OCT_6.plusHours(2));
        db.flush();
        db.clear();

        SocialFriendship again = friendships.findBetween(an, binh).orElseThrow();

        assertThat(again.isAccepted()).isTrue();
        assertThat(again.getStatus()).isEqualTo(SocialFriendship.ACCEPTED);
        assertThat(again.getAcceptedAt()).isEqualTo(OCT_6.plusHours(2));
    }

    @Test
    void findAllOfFindsAStudentsRowsWhicheverSideTheyAreOn() {
        friendships.save(SocialFriendship.request(an, binh, OCT_6));
        friendships.save(SocialFriendship.request(cuong, binh, OCT_6));
        friendships.save(SocialFriendship.request(an, cuong, OCT_6));

        assertThat(friendships.findAllOf(binh)).hasSize(2);
        assertThat(friendships.findAllOf(an)).hasSize(2);
    }

    @Test
    void countRequestsForCountsOnlyRequestsWaitingForThatStudent() {
        friendships.save(SocialFriendship.request(binh, an, OCT_6));
        friendships.save(SocialFriendship.request(an, cuong, OCT_6)); // an sent this one
        SocialFriendship friends = friendships.save(SocialFriendship.request(cuong, binh, OCT_6));
        friends.accept(OCT_6);

        assertThat(friendships.countRequestsFor(an)).isEqualTo(1);
        assertThat(friendships.countRequestsFor(binh)).isZero();
        assertThat(friendships.countRequestsFor(cuong)).isEqualTo(1);
    }

    @Test
    void aStudentCantSendThemselvesARequest() {
        assertThatThrownBy(() -> SocialFriendship.request(an, an, OCT_6)).isInstanceOf(IllegalArgumentException.class);
    }

    /**
     * The table's own rules, on whichever database the tests run on: H2 here, MySQL in GitHub's second run (MigrationTest
     * checks them on a fresh H2 database only). Each bad row names the rule that refused it.
     */
    @ParameterizedTest
    @CsvSource(delimiter = '|', value = {
        "blocked  |                     | ck_social_friendships_status",   // not a status
        "accepted |                     | ck_social_friendships_accepted", // accepted, but no time
        "pending  | 2026-10-06 09:00:00 | ck_social_friendships_accepted"}) // a time, but still pending
    void theTableRefusesBadRows(String status, String acceptedAt, String rule) {
        Timestamp accepted = acceptedAt == null ? null : Timestamp.valueOf(acceptedAt);

        assertThatThrownBy(() -> jdbc.update("INSERT INTO social_friendships"
                + " (user_low_id, user_high_id, requested_by_id, status, created_at, accepted_at)"
                + " VALUES (?, ?, ?, ?, '2026-10-06 08:00:00', ?)", an, binh, an, status, accepted))
                .isInstanceOf(DataAccessException.class)
                .hasMessageContaining(rule);
    }

    @Test
    void theTableKeepsOneRowPerPair() {
        friendships.saveAndFlush(SocialFriendship.request(an, binh, OCT_6));

        assertThatThrownBy(() -> jdbc.update("INSERT INTO social_friendships"
                + " (user_low_id, user_high_id, requested_by_id, status, created_at)"
                + " VALUES (?, ?, ?, 'pending', '2026-10-06 08:00:00')", an, binh, binh))
                .isInstanceOf(DataAccessException.class)
                .hasMessageContaining("uq_social_friendships_pair");
    }
}
