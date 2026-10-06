package vn.edu.hcmiu.sla.social.friends;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;

import vn.edu.hcmiu.sla.auth.User;

/**
 * Accounts found by display name for Find people (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md,
 * 4.2): never the one searching, sorted by name. pattern comes from {@link Friends#containsPattern}, with '!' as
 * LIKE's escape character. On MySQL the column's collation also ignores accents.
 */
public interface PeopleSearch extends Repository<User, Integer> {

    String MATCHING = "from User u where u.id <> :userId and lower(u.displayName) like :pattern escape '!'";

    @Query(value = "select u " + MATCHING + " order by lower(u.displayName), u.id",
            countQuery = "select count(u) " + MATCHING)
    Page<User> findByName(Integer userId, String pattern, Pageable pageable);
}
