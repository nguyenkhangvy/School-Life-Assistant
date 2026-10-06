package vn.edu.hcmiu.sla.core;

import java.util.ArrayList;
import java.util.List;
import java.util.function.IntFunction;

import org.springframework.data.domain.Page;

/**
 * One page of a long list: the "Showing 21–40 of 156 groups" line and the links to the other pages, for the
 * {@code pager} fragment. Page numbers start at 1 in links and URLs (Spring Data's start at 0).
 */
public record Paging(int page, long first, long last, long total, String previous, String next, List<Link> links) {

    static final int ALL_LINKS_UP_TO = 7; // more pages than this: the first, the last, and the current one's neighbours
    public static final int MAX_PAGE = 1_000_000; // far past any real list; page × 100 rows still fits an int

    /** A link to a page; href is null for a gap ("…"). */
    public record Link(String label, String href, boolean current) {
    }

    /** href writes the link to a page, given its number from 1. */
    public static Paging of(Page<?> page, IntFunction<String> href) {
        int number = page.getNumber() + 1;
        int pages = page.getTotalPages();
        long offset = (long) page.getNumber() * page.getSize();
        long first = page.getNumberOfElements() == 0 ? 0 : offset + 1;
        long last = offset + page.getNumberOfElements();
        List<Link> links = new ArrayList<>();
        int lastShown = 0;
        for (int n = 1; n <= pages; n++) {
            if (pages > ALL_LINKS_UP_TO && n != 1 && n != pages && Math.abs(n - number) > 1) {
                continue;
            }
            if (lastShown != 0 && n > lastShown + 1) {
                links.add(new Link("…", null, false));
            }
            links.add(new Link(String.valueOf(n), href.apply(n), n == number));
            lastShown = n;
        }
        return new Paging(number, first, last, page.getTotalElements(), number > 1 ? href.apply(number - 1) : null,
                number < pages ? href.apply(number + 1) : null, links);
    }

    /** "Showing 21–40 of 156 groups", "Showing 41 of 41 groups", "Showing 1 of 1 person". */
    public String showing(String one, String many) {
        String rows = first == last ? String.valueOf(first) : first + "–" + last;
        return "Showing " + rows + " of " + total + " " + (total == 1 ? one : many);
    }

    /**
     * The page number in a URL: "3" is 3; missing, not a number, or below 1 is 1; anything above {@link #MAX_PAGE} is
     * MAX_PAGE, which a list then turns into its last page.
     */
    public static int number(String text) {
        String digits = text == null ? "" : text.strip();
        if (!digits.matches("\\d+")) {
            return 1;
        }
        digits = digits.replaceFirst("^0+(?=\\d)", "");
        return digits.length() > 7 ? MAX_PAGE : Math.max(1, Math.min(MAX_PAGE, Integer.parseInt(digits)));
    }
}
