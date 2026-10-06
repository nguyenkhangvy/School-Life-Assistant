package vn.edu.hcmiu.sla.social.model;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * Two students: a friend request, or friends (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md, 3.1).
 * One row per pair, the smaller user id first, whichever way the request went; this class keeps that order.
 */
@Entity
@Table(name = "social_friendships")
public class SocialFriendship {

    public static final String PENDING = "pending";
    public static final String ACCEPTED = "accepted";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "user_low_id", nullable = false)
    private Integer userLowId;

    @Column(name = "user_high_id", nullable = false)
    private Integer userHighId;

    @Column(name = "requested_by_id", nullable = false)
    private Integer requestedById;

    @Column(nullable = false, length = 8)
    private String status;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt; // UTC, when the request was sent

    @Column(name = "accepted_at")
    private LocalDateTime acceptedAt; // UTC

    protected SocialFriendship() {
    }

    /** A request from one student to another, sent now and not answered yet. */
    public static SocialFriendship request(Integer from, Integer to, LocalDateTime now) {
        if (from.equals(to)) {
            throw new IllegalArgumentException("A student can't send a friend request to themselves");
        }
        SocialFriendship friendship = new SocialFriendship();
        friendship.userLowId = Math.min(from, to);
        friendship.userHighId = Math.max(from, to);
        friendship.requestedById = from;
        friendship.status = PENDING;
        friendship.createdAt = now;
        return friendship;
    }

    /** The two are friends from now on. */
    public void accept(LocalDateTime now) {
        status = ACCEPTED;
        acceptedAt = now;
    }

    /** The other student of the pair. */
    public Integer other(Integer userId) {
        return userId.equals(userLowId) ? userHighId : userLowId;
    }

    public boolean isPending() {
        return PENDING.equals(status);
    }

    public boolean isAccepted() {
        return ACCEPTED.equals(status);
    }

    public boolean isSentBy(Integer userId) {
        return requestedById.equals(userId);
    }

    public Integer getId() {
        return id;
    }

    public Integer getUserLowId() {
        return userLowId;
    }

    public Integer getUserHighId() {
        return userHighId;
    }

    public Integer getRequestedById() {
        return requestedById;
    }

    public String getStatus() {
        return status;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public LocalDateTime getAcceptedAt() {
        return acceptedAt;
    }
}
