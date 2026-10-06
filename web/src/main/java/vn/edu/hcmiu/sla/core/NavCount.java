package vn.edu.hcmiu.sla.core;

import java.util.function.ToIntFunction;

/**
 * A number after a module's menu label for the logged-in student, such as friend requests waiting. A module adds one
 * bean next to its {@link NavModule}:
 * <pre>
 * &#64;Bean NavCount friendsCount(Friends friends) { return new NavCount("Friends", friends::countRequestsFor); }
 * </pre>
 * 0 shows nothing.
 */
public record NavCount(String label, ToIntFunction<Integer> perUser) {

    public int of(Integer userId) {
        return perUser.applyAsInt(userId);
    }
}
