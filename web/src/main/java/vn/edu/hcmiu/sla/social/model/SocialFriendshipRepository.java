package vn.edu.hcmiu.sla.social.model;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

/** Friend requests and friendships; a pair is found whichever of the two asks. */
public interface SocialFriendshipRepository extends JpaRepository<SocialFriendship, Integer> {

    @Query("select f from SocialFriendship f where f.userLowId = :low and f.userHighId = :high")
    Optional<SocialFriendship> findPair(Integer low, Integer high);

    /** The row between these two students, if any. */
    default Optional<SocialFriendship> findBetween(Integer a, Integer b) {
        return findPair(Math.min(a, b), Math.max(a, b));
    }

    /** Every request and friendship the student is part of, whichever side they are on. */
    @Query("select f from SocialFriendship f where f.userLowId = :userId or f.userHighId = :userId")
    List<SocialFriendship> findAllOf(Integer userId);

    /** Requests sent to this student that they haven't answered, from active Students only (site roles spec, 5.2). */
    @Query("select count(f) from SocialFriendship f, User u where u.id = f.requestedById and f.status = 'pending'"
            + " and f.requestedById <> :userId and (f.userLowId = :userId or f.userHighId = :userId)"
            + " and u.role = 'student' and u.deactivatedAt is null")
    long countRequestsFor(Integer userId);
}
