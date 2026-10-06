package vn.edu.hcmiu.sla.social.pages;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.LocalDateTime;
import java.util.Optional;
import java.util.function.Supplier;

import org.springframework.dao.ConcurrencyFailureException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Page;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.core.Flash;
import vn.edu.hcmiu.sla.core.Paging;
import vn.edu.hcmiu.sla.core.Text;
import vn.edu.hcmiu.sla.social.friends.Friends;
import vn.edu.hcmiu.sla.social.friends.Friends.PersonRow;
import vn.edu.hcmiu.sla.social.friends.Friends.Result;

/**
 * The Friends page (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md, 4.2): find people by display
 * name, answer requests, and your friends. An unknown person, or yourself, is 404.
 */
@Controller
@RequestMapping("/social/friends")
public class FriendsController {

    private final Clock clock;
    private final Friends friends;

    public FriendsController(Clock clock, Friends friends) {
        this.clock = clock;
        this.friends = friends;
    }

    private LocalDateTime now() {
        return LocalDateTime.now(clock);
    }

    private static ResponseStatusException notFound() {
        return new ResponseStatusException(HttpStatus.NOT_FOUND);
    }

    /**
     * The page with a search: "/social/friends?q=Lan%20Anh&page=2". URLEncoder writes a space as +, which means a space
     * only in a query; %20 means a space anywhere in a URL, so the link is written with %20.
     */
    static String searchLink(String query, int page) {
        return "/social/friends?q=" + URLEncoder.encode(query, StandardCharsets.UTF_8).replace("+", "%20")
                + "&page=" + page;
    }

    @GetMapping
    String friends(@AuthenticationPrincipal AppUser user, @RequestParam(defaultValue = "") String q,
            @RequestParam(defaultValue = "1") String page, Model model) {
        String query = Text.strip(q);
        model.addAttribute("q", query);
        if (!query.isEmpty()) {
            if (query.codePointCount(0, query.length()) < Friends.MIN_SEARCH) {
                model.addAttribute("searchError", "Type at least 2 letters.");
            } else {
                Page<PersonRow> found = friends.search(user.id(), query, Paging.number(page));
                model.addAttribute("results", found.getContent());
                model.addAttribute("paging", Paging.of(found, n -> searchLink(query, n)));
            }
        }
        model.addAttribute("forYou", friends.requestsFor(user.id()));
        model.addAttribute("sent", friends.requestsSentBy(user.id()));
        model.addAttribute("friends", friends.friendsOf(user.id()));
        return "social/friends";
    }

    @PostMapping("/{userId}/add")
    String add(@AuthenticationPrincipal AppUser user, @PathVariable int userId,
            @RequestParam(defaultValue = "") String q, @RequestParam(defaultValue = "1") String page,
            RedirectAttributes redirect) {
        return answer(redirect, q, page, () -> friends.add(user.id(), userId, now()));
    }

    @PostMapping("/{userId}/accept")
    String accept(@AuthenticationPrincipal AppUser user, @PathVariable int userId,
            @RequestParam(defaultValue = "") String q, @RequestParam(defaultValue = "1") String page,
            RedirectAttributes redirect) {
        return answer(redirect, q, page, () -> friends.accept(user.id(), userId, now()));
    }

    @PostMapping("/{userId}/decline")
    String decline(@AuthenticationPrincipal AppUser user, @PathVariable int userId,
            @RequestParam(defaultValue = "") String q, @RequestParam(defaultValue = "1") String page,
            RedirectAttributes redirect) {
        return answer(redirect, q, page, () -> friends.decline(user.id(), userId, now()));
    }

    @PostMapping("/{userId}/cancel")
    String cancel(@AuthenticationPrincipal AppUser user, @PathVariable int userId,
            @RequestParam(defaultValue = "") String q, @RequestParam(defaultValue = "1") String page,
            RedirectAttributes redirect) {
        return answer(redirect, q, page, () -> friends.cancel(user.id(), userId, now()));
    }

    @PostMapping("/{userId}/remove")
    String remove(@AuthenticationPrincipal AppUser user, @PathVariable int userId,
            @RequestParam(defaultValue = "") String q, @RequestParam(defaultValue = "1") String page,
            RedirectAttributes redirect) {
        return answer(redirect, q, page, () -> friends.remove(user.id(), userId, now()));
    }

    /**
     * Runs a button and goes back to the page (to the search it was pressed in, if any) with what happened. Another
     * click at the same moment (a double click, the other student, a second tab) may have saved the same pair first, so
     * the unique key refuses this insert, or deleted the row this click had just read, so its update or delete finds
     * nothing. Running the button again then sees the row as it is now and says what that means.
     */
    private String answer(RedirectAttributes redirect, String q, String page, Supplier<Optional<Result>> button) {
        Result result;
        try {
            result = button.get().orElseThrow(FriendsController::notFound);
        } catch (DataIntegrityViolationException | ConcurrencyFailureException otherClick) {
            result = button.get().orElseThrow(FriendsController::notFound);
        }
        if (result.ok()) {
            Flash.success(redirect, result.message());
        } else {
            Flash.error(redirect, result.message());
        }
        String query = Text.strip(q);
        return "redirect:" + (query.isEmpty() ? "/social/friends" : searchLink(query, Paging.number(page)));
    }
}
