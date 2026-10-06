package vn.edu.hcmiu.sla.social.friends;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.function.Predicate;
import java.util.stream.Collectors;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.auth.User;
import vn.edu.hcmiu.sla.auth.UserRepository;
import vn.edu.hcmiu.sla.social.model.SocialFriendship;
import vn.edu.hcmiu.sla.social.model.SocialFriendshipRepository;

/**
 * Friends (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md, 4.2 and 6.4): finding people by display
 * name, friend requests and friends. Every button is safe to press twice or from an out-of-date page: it does what
 * still makes sense and says what happened.
 */
@Service
public class Friends {

    public static final int PAGE_SIZE = 20;
    public static final int MIN_SEARCH = 2; // letters a search needs, so nobody lists every account at once

    /** Where a person stands with the student, for the button on their row. */
    public enum Standing { NONE, SENT, RECEIVED, FRIENDS }

    /** A search result: a name only, never an email. */
    public record PersonRow(Integer id, String name, Standing standing) {
    }

    /** A friend request: the other person and when it was sent (UTC). */
    public record Request(Integer userId, String name, LocalDateTime sentAt) {
    }

    public record Friend(Integer userId, String name) {
    }

    /** What a button did; ok false shows the message as an error. */
    public record Result(boolean ok, String message) {
    }

    private final SocialFriendshipRepository friendships;
    private final PeopleSearch people;
    private final UserRepository users;

    public Friends(SocialFriendshipRepository friendships, PeopleSearch people, UserRepository users) {
        this.friendships = friendships;
        this.people = people;
        this.users = users;
    }

    /** "%vy%" for "Vy": anywhere in the name, lower case, with LIKE's own characters (and '!') taken literally. */
    static String containsPattern(String query) {
        String text = query.toLowerCase(Locale.ROOT).replace("!", "!!").replace("%", "!%").replace("_", "!_");
        return "%" + text + "%";
    }

    /** People whose display name holds the query, 20 a page; a page past the end gives the last one. */
    @Transactional(readOnly = true)
    public Page<PersonRow> search(Integer userId, String query, int page) {
        String pattern = containsPattern(query);
        Page<User> found = people.findByName(userId, pattern, PageRequest.of(Math.max(page, 1) - 1, PAGE_SIZE));
        if (found.getTotalPages() > 0 && found.getNumber() >= found.getTotalPages()) {
            found = people.findByName(userId, pattern, PageRequest.of(found.getTotalPages() - 1, PAGE_SIZE));
        }
        Map<Integer, Standing> standings = new HashMap<>();
        for (SocialFriendship row : friendships.findAllOf(userId)) {
            standings.put(row.other(userId), row.isAccepted() ? Standing.FRIENDS
                    : row.isSentBy(userId) ? Standing.SENT : Standing.RECEIVED);
        }
        return found.map(user -> new PersonRow(user.getId(), user.getDisplayName(),
                standings.getOrDefault(user.getId(), Standing.NONE)));
    }

    /** Requests waiting for the student, newest first. */
    @Transactional(readOnly = true)
    public List<Request> requestsFor(Integer userId) {
        return requests(userId, row -> row.isPending() && !row.isSentBy(userId));
    }

    /** Requests the student sent that aren't answered, newest first. */
    @Transactional(readOnly = true)
    public List<Request> requestsSentBy(Integer userId) {
        return requests(userId, row -> row.isPending() && row.isSentBy(userId));
    }

    private List<Request> requests(Integer userId, Predicate<SocialFriendship> which) {
        List<SocialFriendship> rows = friendships.findAllOf(userId).stream().filter(which)
                .sorted(Comparator.comparing(SocialFriendship::getCreatedAt).reversed()
                        .thenComparing(SocialFriendship::getId, Comparator.reverseOrder()))
                .toList();
        Map<Integer, String> names = names(rows.stream().map(row -> row.other(userId)).toList());
        return rows.stream().map(row -> new Request(row.other(userId), names.get(row.other(userId)), row.getCreatedAt()))
                .toList();
    }

    /** The student's friends, by name (case ignored). */
    @Transactional(readOnly = true)
    public List<Friend> friendsOf(Integer userId) {
        List<Integer> ids = friendships.findAllOf(userId).stream().filter(SocialFriendship::isAccepted)
                .map(row -> row.other(userId)).toList();
        Map<Integer, String> names = names(ids);
        return ids.stream().map(id -> new Friend(id, names.get(id)))
                .sorted(Comparator.comparing((Friend friend) -> friend.name().toLowerCase(Locale.ROOT))
                        .thenComparing(Friend::userId))
                .toList();
    }

    /** Friend requests waiting for the student: the number after Friends in the menu. */
    @Transactional(readOnly = true)
    public int countRequestsFor(Integer userId) {
        return (int) friendships.countRequestsFor(userId);
    }

    private Map<Integer, String> names(Collection<Integer> ids) {
        return users.findAllById(ids).stream().collect(Collectors.toMap(User::getId, User::getDisplayName));
    }

    /** The other person's display name; empty for an unknown id or the student themselves. */
    private Optional<String> nameOf(Integer userId, Integer otherId) {
        return otherId.equals(userId) ? Optional.empty() : users.findById(otherId).map(User::getDisplayName);
    }

    private static Optional<Result> ok(String message) {
        return Optional.of(new Result(true, message));
    }

    private static Optional<Result> error(String message) {
        return Optional.of(new Result(false, message));
    }

    private static final String NOT_WAITING = "That request is no longer waiting.";

    @Transactional
    public Optional<Result> add(Integer userId, Integer otherId, LocalDateTime now) {
        Optional<String> name = nameOf(userId, otherId);
        if (name.isEmpty()) {
            return Optional.empty();
        }
        Optional<SocialFriendship> row = friendships.findBetween(userId, otherId);
        if (row.isEmpty()) {
            friendships.saveAndFlush(SocialFriendship.request(userId, otherId, now));
            return ok("Friend request sent to " + name.get() + ".");
        }
        SocialFriendship friendship = row.get();
        if (friendship.isAccepted()) {
            return ok("You and " + name.get() + " are already friends.");
        }
        if (friendship.isSentBy(userId)) {
            return ok("Friend request sent to " + name.get() + ".");
        }
        friendship.accept(now);
        return ok("You and " + name.get() + " are now friends.");
    }

    @Transactional
    public Optional<Result> accept(Integer userId, Integer otherId, LocalDateTime now) {
        Optional<String> name = nameOf(userId, otherId);
        if (name.isEmpty()) {
            return Optional.empty();
        }
        Optional<SocialFriendship> row = friendships.findBetween(userId, otherId);
        if (row.isPresent() && row.get().isAccepted()) {
            return ok("You and " + name.get() + " are already friends.");
        }
        if (row.isEmpty() || row.get().isSentBy(userId)) {
            return error(NOT_WAITING);
        }
        row.get().accept(now);
        return ok("You and " + name.get() + " are now friends.");
    }

    @Transactional
    public Optional<Result> decline(Integer userId, Integer otherId, LocalDateTime now) {
        Optional<String> name = nameOf(userId, otherId);
        if (name.isEmpty()) {
            return Optional.empty();
        }
        Optional<SocialFriendship> row = friendships.findBetween(userId, otherId);
        if (row.isPresent() && row.get().isAccepted()) {
            return error("You and " + name.get() + " are already friends.");
        }
        if (row.isPresent() && row.get().isSentBy(userId)) {
            return error(NOT_WAITING);
        }
        row.ifPresent(friendships::delete);
        return ok("Declined " + name.get() + "'s request.");
    }

    @Transactional
    public Optional<Result> cancel(Integer userId, Integer otherId, LocalDateTime now) {
        Optional<String> name = nameOf(userId, otherId);
        if (name.isEmpty()) {
            return Optional.empty();
        }
        Optional<SocialFriendship> row = friendships.findBetween(userId, otherId);
        if (row.isPresent() && row.get().isAccepted()) {
            return error(name.get() + " already accepted: you're friends now.");
        }
        if (row.isPresent() && !row.get().isSentBy(userId)) {
            return error(NOT_WAITING);
        }
        row.ifPresent(friendships::delete);
        return ok("Cancelled your request to " + name.get() + ".");
    }

    @Transactional
    public Optional<Result> remove(Integer userId, Integer otherId, LocalDateTime now) {
        Optional<String> name = nameOf(userId, otherId);
        if (name.isEmpty()) {
            return Optional.empty();
        }
        Optional<SocialFriendship> row = friendships.findBetween(userId, otherId);
        if (row.isPresent() && row.get().isPending()) {
            return error("You and " + name.get() + " aren't friends yet.");
        }
        row.ifPresent(friendships::delete);
        return ok("Removed " + name.get() + " from your friends.");
    }
}
