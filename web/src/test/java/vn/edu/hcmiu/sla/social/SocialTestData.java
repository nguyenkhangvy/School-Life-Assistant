package vn.edu.hcmiu.sla.social;

import java.time.LocalDateTime;

import jakarta.persistence.EntityManager;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.auth.Role;
import vn.edu.hcmiu.sla.auth.User;
import vn.edu.hcmiu.sla.social.model.SocialFriendship;

/**
 * Accounts and friendships for Social tests, saved straight into the test database. Other test classes leave
 * accounts named "An" behind, so searches in tests look for names like "Lan" or "Trang".
 */
public final class SocialTestData {

    static final LocalDateTime SEPT_1 = LocalDateTime.of(2026, 9, 1, 0, 0);

    private final EntityManager db;
    private int people;

    public SocialTestData(EntityManager db) {
        this.db = db;
    }

    /** A new account with this display name; its email is person1@example.com, person2@…, and so on. */
    public AppUser person(String displayName) {
        people++;
        User user = new User("person" + people + "@example.com", displayName, "x", SEPT_1);
        db.persist(user);
        db.flush();
        return AppUser.of(user);
    }

    /** from asked to, at this UTC time; not answered yet. */
    public SocialFriendship request(AppUser from, AppUser to, LocalDateTime at) {
        SocialFriendship request = SocialFriendship.request(from.id(), to.id(), at);
        db.persist(request);
        db.flush();
        return request;
    }

    /** That account deactivated, as an Admin would do it (site roles spec, 5.2). */
    public void deactivate(AppUser person) {
        db.find(User.class, person.id()).deactivate(null, SEPT_1);
        db.flush();
    }

    public void reactivate(AppUser person) {
        db.find(User.class, person.id()).reactivate(null, SEPT_1);
        db.flush();
    }

    /** That account given another role. */
    public void giveRole(AppUser person, Role role) {
        db.find(User.class, person.id()).changeRole(role, null, SEPT_1);
        db.flush();
    }

    /** a and b are friends (a asked). */
    public SocialFriendship friends(AppUser a, AppUser b) {
        SocialFriendship friendship = SocialFriendship.request(a.id(), b.id(), SEPT_1);
        friendship.accept(SEPT_1);
        db.persist(friendship);
        db.flush();
        return friendship;
    }
}
