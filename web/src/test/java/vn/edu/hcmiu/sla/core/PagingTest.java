package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

import java.util.Collections;
import java.util.function.IntFunction;

import org.junit.jupiter.api.Test;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

import vn.edu.hcmiu.sla.core.Paging.Link;

class PagingTest {

    static final IntFunction<String> HREF = n -> "/list?page=" + n;

    /** Page number (from 1) of a list of total rows, size rows a page. */
    static Page<String> page(int number, int size, long total) {
        int rows = (int) Math.max(0, Math.min(size, total - (long) (number - 1) * size));
        return new PageImpl<>(Collections.nCopies(rows, "row"), PageRequest.of(number - 1, size), total);
    }

    @Test
    void showingNamesTheRowsOnThisPage() {
        Paging paging = Paging.of(page(2, 20, 156), HREF);

        assertThat(paging.showing("group", "groups")).isEqualTo("Showing 21–40 of 156 groups");
        assertThat(paging.page()).isEqualTo(2);
    }

    @Test
    void aPageWithOneRowAndASingleResult() {
        assertThat(Paging.of(page(3, 20, 41), HREF).showing("group", "groups")).isEqualTo("Showing 41 of 41 groups");
        assertThat(Paging.of(page(1, 20, 1), HREF).showing("person", "people")).isEqualTo("Showing 1 of 1 person");
    }

    @Test
    void previousAndNextLinkTheNeighbours() {
        Paging middle = Paging.of(page(2, 20, 156), HREF);
        assertThat(middle.previous()).isEqualTo("/list?page=1");
        assertThat(middle.next()).isEqualTo("/list?page=3");

        assertThat(Paging.of(page(1, 20, 156), HREF).previous()).isNull();
        assertThat(Paging.of(page(8, 20, 156), HREF).next()).isNull();
    }

    @Test
    void upToSevenPagesAreAllLinked() {
        assertThat(Paging.of(page(1, 20, 140), HREF).links())
                .extracting(Link::label, Link::current)
                .containsExactly(tuple("1", true), tuple("2", false), tuple("3", false), tuple("4", false),
                        tuple("5", false), tuple("6", false), tuple("7", false));
    }

    @Test
    void morePagesLinkBothEndsAndTheNeighbours() {
        assertThat(Paging.of(page(5, 20, 200), HREF).links())
                .extracting(Link::label, Link::href, Link::current)
                .containsExactly(tuple("1", "/list?page=1", false), tuple("…", null, false),
                        tuple("4", "/list?page=4", false), tuple("5", "/list?page=5", true),
                        tuple("6", "/list?page=6", false), tuple("…", null, false), tuple("10", "/list?page=10", false));
    }

    @Test
    void oneShortPageHasNoLinksToShow() {
        assertThat(Paging.of(page(1, 20, 5), HREF).links()).hasSize(1);
        assertThat(Paging.of(page(1, 20, 0), HREF).links()).isEmpty();
    }

    @Test
    void pageNumbersInTheUrl() {
        assertThat(Paging.number("3")).isEqualTo(3);
        assertThat(Paging.number(" 2 ")).isEqualTo(2);
        assertThat(Paging.number("")).isEqualTo(1);
        assertThat(Paging.number("abc")).isEqualTo(1);
        assertThat(Paging.number("0")).isEqualTo(1);
        assertThat(Paging.number("-2")).isEqualTo(1);
        assertThat(Paging.number("99999999999")).isEqualTo(1);
    }
}
