package vn.edu.hcmiu.sla.school.mail;

import static org.assertj.core.api.Assertions.assertThat;
import static vn.edu.hcmiu.sla.school.mail.MailboxTest.NOW_IN_VIETNAM;
import static vn.edu.hcmiu.sla.school.mail.MailboxTest.TODAY;
import static vn.edu.hcmiu.sla.school.mail.MailboxTest.box;
import static vn.edu.hcmiu.sla.school.mail.MailboxTest.keys;
import static vn.edu.hcmiu.sla.school.mail.MailboxTest.session;

import java.time.LocalDate;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

import vn.edu.hcmiu.sla.school.mail.Mailbox.Card;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Deadline;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Found;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Mine;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Period;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Session;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Tag;
import vn.edu.hcmiu.sla.school.mail.Mailbox.View;
import vn.edu.hcmiu.sla.school.mail.MailboxTest.Mail;
import vn.edu.hcmiu.sla.school.model.SchoolMail;

/**
 * Cards with Periods, deadlines and flags (spec 2026-10-07-mail-event-kinds-design.md, 6.2): which are event-like,
 * their tags, next date and Past. Today is Mon 28/09/2026, 08:00 in Vietnam.
 */
class MailboxEventKindsTest {

    final Map<String, List<Session>> sessions = new HashMap<>();
    final Map<String, List<Period>> periods = new HashMap<>();
    final Map<String, List<Deadline>> deadlines = new HashMap<>();
    Set<String> joined = Set.of();
    Set<String> added = Set.of();

    View build(Mail... mails) {
        List<SchoolMail> rows = new ArrayList<>(Arrays.stream(mails).map(Mail::row).toList());
        rows.sort(Comparator.comparing(SchoolMail::getReceivedAt).reversed());
        return Mailbox.build(rows, Map.of(), new Found(sessions, periods, deadlines), new Mine(joined, added),
                NOW_IN_VIETNAM);
    }

    /** A deadline on the day `daysFromToday` from today, at "17:00" (or none). */
    static Deadline deadline(String kind, int daysFromToday, String time, String mode) {
        return new Deadline(kind, TODAY.plusDays(daysFromToday), time == null ? null : LocalTime.parse(time), mode);
    }

    static Period period(int firstDay, int lastDay, String mode, String from, String to) {
        return new Period(TODAY.plusDays(firstDay), TODAY.plusDays(lastDay), mode, from == null ? null
                : LocalTime.parse(from), to == null ? null : LocalTime.parse(to), false, null);
    }

    static List<String> tags(Card card) {
        return card.tags().stream().map(Tag::text).toList();
    }

    // ---- event-like ---------------------------------------------------------------------------------------------

    @Test
    void aLecturersMeetingWithATimeIsEventLike() {
        sessions.put("meet", List.of(session(1, "09:00", "10:00")));
        sessions.put("notice", List.of(session(1, "13:00", null)));
        View view = build(new Mail("meet", 1, "class").lecturer().meeting(), new Mail("notice", 2, "class").lecturer(),
                new Mail("untimed", 3, "class").lecturer().meeting());

        Card meeting = view.card("meet");
        assertThat(List.of(meeting.eventLike(), meeting.joinable(), meeting.doneWhenOpened()))
                .containsExactly(true, true, false);
        assertThat(meeting.sessions()).containsExactly(session(1, "09:00", "10:00"));
        assertThat(meeting.nextDate()).isEqualTo(TODAY.plusDays(1));
        assertThat(keys(box(view, "lecturers").cards())).containsExactly("meet", "notice", "untimed");
        assertThat(List.of(view.card("notice").eventLike(), view.card("untimed").eventLike()))
                .containsExactly(false, false);
        assertThat(view.card("notice").sessions()).isEmpty();
    }

    @Test
    void aSessionKeepsWhatTheLaptopFound() {
        Session found = new Session(TODAY.plusDays(1), LocalTime.of(13, 30), LocalTime.of(15, 30), true, false,
                LocalTime.of(13, 0), null, "in_person", null, "round_1");
        sessions.put("contest", List.of(found));

        assertThat(build(new Mail("contest", 1, "event")).card("contest").sessions()).containsExactly(found);
    }

    // ---- registration and other deadlines -----------------------------------------------------------------------

    @Test
    void beforeItOpensTheTagSaysWhenItOpensAndCloses() {
        deadlines.put("talk", List.of(deadline("opens", 2, "08:00", null), deadline("register", 5, null, null)));

        Card card = build(new Mail("talk", 1, "event").on(9)).card("talk");

        assertThat(tags(card)).containsExactly("Registration opens Wed 30/09, closes Sat 03/10");
        assertThat(List.of(card.closed(), card.past())).containsExactly(false, false);
    }

    @Test
    void whileOpenTheTagSaysByWhen() {
        deadlines.put("talk", List.of(deadline("opens", -1, null, null), deadline("register", 5, "17:00", null)));
        deadlines.put("today", List.of(deadline("register", 0, "09:00", null)));
        deadlines.put("open", List.of(deadline("opens", 0, null, null)));

        View view = build(new Mail("talk", 1, "event").on(9), new Mail("today", 2, "event").on(9),
                new Mail("open", 3, "event").on(9));

        assertThat(tags(view.card("talk"))).containsExactly("Register by 17:00 Sat 03/10");
        assertThat(tags(view.card("today"))).containsExactly("Register by 09:00 Mon 28/09");
        assertThat(tags(view.card("open"))).containsExactly("Registration open");
    }

    @Test
    void eachModesDeadlineIsShownAndAPassedOneStruckOut() {
        deadlines.put("contest", List.of(deadline("register", 0, "07:00", "in_person"),
                deadline("register", 3, "17:00", "online")));

        Card card = build(new Mail("contest", 1, "event").on(9)).card("contest");

        Tag tag = card.tags().get(0);
        assertThat(tag.text()).isEqualTo("Register by: In person 07:00 Mon 28/09 · Online 17:00 Thu 01/10");
        assertThat(tag.pieces()).extracting(piece -> piece.passed()).containsExactly(true, false);
        assertThat(card.closed()).isFalse();
    }

    @Test
    void registrationClosesAtItsTimeOrAtTheEndOfItsDay() {
        deadlines.put("morning", List.of(deadline("register", 0, "07:59", null)));
        deadlines.put("today", List.of(deadline("register", 0, null, null)));
        sessions.put("morning", List.of(session(3, "09:00", null)));
        sessions.put("today", List.of(session(3, "09:00", null)));

        View view = build(new Mail("morning", 1, "event"), new Mail("today", 2, "event"));

        assertThat(List.of(view.card("morning").closed(), view.card("morning").past())).containsExactly(true, true);
        assertThat(tags(view.card("morning"))).containsExactly("Registration closed");
        assertThat(List.of(view.card("today").closed(), view.card("today").past())).containsExactly(false, false);
        assertThat(view.card("morning").doneWhenOpened()).isFalse();
    }

    @Test
    void aReminderCanExtendTheRegistration() {
        deadlines.put("first", List.of(deadline("register", -1, null, null)));
        deadlines.put("reminder", List.of(deadline("register", 2, "12:00", null)));

        Card card = build(new Mail("reminder", 1, "event").thread("T").on(4),
                new Mail("first", 30, "event").thread("T").on(4)).card("reminder");

        assertThat(List.of(card.closed(), card.past())).containsExactly(false, false);
        assertThat(tags(card)).containsExactly("Register by 12:00 Wed 30/09");
        assertThat(card.registerBy()).isEqualTo(TODAY.plusDays(2));
    }

    @Test
    void anOlderAgentsEmailHasItsRegistrationDayOnly() {
        Card card = build(new Mail("talk", 1, "event").on(3).registerBy(1)).card("talk");

        assertThat(card.deadlines()).containsExactly(deadline("register", 1, null, null));
        assertThat(tags(card)).containsExactly("Register by Tue 29/09");
    }

    @Test
    void confirmAndDueShowWhileTheirTimeHasNotPassed() {
        deadlines.put("task", List.of(deadline("due", -1, null, null), deadline("confirm", 1, null, null),
                deadline("due", 3, "23:59", null), deadline("due", 6, null, null)));

        Card card = build(new Mail("task", 1, "school_task").on(9)).card("task");

        assertThat(tags(card)).containsExactly("Confirm by Tue 29/09", "Due 23:59 Thu 01/10");
    }

    @Test
    void dueByModeShowsEachMode() {
        deadlines.put("report", List.of(deadline("due", 2, "17:00", "in_person"), deadline("due", 4, null, "online")));

        assertThat(tags(build(new Mail("report", 1, "class").lecturer()).card("report")))
                .containsExactly("Due: In person 17:00 Wed 30/09 · Online Fri 02/10");
    }

    @Test
    void aRegisteredCardShowsNoRegistrationAndNeverClosesIntoPast() {
        deadlines.put("talk", List.of(deadline("register", -2, null, null), deadline("confirm", 1, null, null)));
        sessions.put("talk", List.of(session(3, "09:00", null)));

        Card card = build(new Mail("talk", 1, "event").registered()).card("talk");

        assertThat(List.of(card.registered(), card.closed(), card.past())).containsExactly(true, true, false);
        assertThat(tags(card)).containsExactly("Confirm by Tue 29/09");
    }

    @Test
    void anEventWhoseRegistrationClosedStaysWhenAPeriodWasAdded() {
        deadlines.put("fair", List.of(deadline("register", -2, null, null)));
        periods.put("fair", List.of(period(2, 4, "all_day", null, null)));
        added = Set.of("fair");

        Card card = build(new Mail("fair", 1, "event")).card("fair");

        assertThat(List.of(card.closed(), card.added(), card.past())).containsExactly(true, true, false);
        assertThat(tags(card)).isEmpty();
    }

    // ---- Periods ------------------------------------------------------------------------------------------------

    @Test
    void aRunningPeriodsNextDateIsToday() {
        periods.put("running", List.of(period(-2, 2, "daily_window", "09:00", "17:00")));
        periods.put("later", List.of(period(3, 5, "all_day", null, null)));
        sessions.put("later", List.of(session(4, "13:00", null)));

        View view = build(new Mail("running", 1, "event").on(-2, 2), new Mail("later", 2, "event"));

        assertThat(view.card("running").nextDate()).isEqualTo(TODAY);
        assertThat(view.card("later").nextDate()).isEqualTo(TODAY.plusDays(3));
        assertThat(keys(box(view, "events").cards())).containsExactly("running", "later");
    }

    @Test
    void aCardIsPastWhenEverySessionAndPeriodHasEnded() {
        periods.put("over", List.of(period(-3, -1, "all_day", null, null)));
        periods.put("ending", List.of(period(-3, 0, "daily_window", "06:00", "07:30")));
        periods.put("today", List.of(period(-3, 0, "all_day", null, null)));

        View view = build(new Mail("over", 1, "event").on(5), new Mail("ending", 2, "event"),
                new Mail("today", 3, "event"));

        assertThat(keys(box(view, "events").past())).containsExactlyInAnyOrder("over", "ending");
        assertThat(keys(box(view, "events").cards())).containsExactly("today");
        assertThat(view.card("over").periods()).isEmpty();
    }

    @Test
    void onlyEventLikeCardsShowPeriods() {
        periods.put("promo", List.of(period(1, 5, "all_day", null, null)));

        Card card = build(new Mail("promo", 1, "promotion").on(1, 5)).card("promo");

        assertThat(card.periods()).isEmpty();
        assertThat(card.nextDate()).isEqualTo(TODAY.plusDays(1));
    }

    @Test
    void aCardWithOnePeriodAndNoSessionsCanBeAddedFromItsRow() {
        periods.put("one", List.of(period(1, 5, "all_day", null, null)));
        periods.put("two", List.of(period(1, 5, "all_day", null, null), period(6, 6, "one_window", "09:00", "11:00")));
        periods.put("timed", List.of(period(1, 5, "all_day", null, null)));
        sessions.put("timed", List.of(session(2, "09:00", null)));

        View view = build(new Mail("one", 1, "event"), new Mail("two", 2, "event"), new Mail("timed", 3, "event"));

        assertThat(List.of("one", "two", "timed")).map(k -> view.card(k).addable()).containsExactly(true, false, false);
    }

    @Test
    void aThreadsPeriodsAreKeptOnce() {
        periods.put("new", List.of(period(1, 5, "daily_window", "09:00", "17:00")));
        periods.put("old", List.of(period(1, 5, "daily_window", "09:00", "17:00"),
                period(1, 5, "daily_window", "13:00", "16:00")));

        Card card = build(new Mail("new", 1, "event").thread("T"), new Mail("old", 5, "event").thread("T")).card("new");

        assertThat(card.periods()).extracting(Period::id).containsExactly("2026-09-29/2026-10-03/daily_window/09:00",
                "2026-09-29/2026-10-03/daily_window/13:00");
    }

    // ---- Outlook invitations ------------------------------------------------------------------------------------

    @Test
    void aCancelledMeetingCantBeJoinedUnlessSomethingWasJoined() {
        sessions.put("request", List.of(session(1, "09:00", "10:00")));

        View view = build(new Mail("cancel", 1, "class").lecturer().meeting().thread("T").invitation("cancelled"),
                new Mail("request", 5, "class").lecturer().meeting().thread("T").invitation("request"));
        joined = Set.of("request");
        View joinedView = build(new Mail("cancel", 1, "class").lecturer().meeting().thread("T").invitation("cancelled"),
                new Mail("request", 5, "class").lecturer().meeting().thread("T").invitation("request"));

        Card card = view.card("cancel");
        assertThat(List.of(card.cancelled(), card.eventLike(), card.joinable())).containsExactly(true, true, false);
        assertThat(card.sessions()).containsExactly(session(1, "09:00", "10:00"));
        assertThat(joinedView.card("cancel").joinable()).isTrue();
    }

    @Test
    void anEarlierCancellationDoesNotCancelANewerRequest() {
        sessions.put("again", List.of(session(1, "09:00", "10:00")));

        Card card = build(new Mail("again", 1, "class").lecturer().meeting().thread("T").invitation("request"),
                new Mail("cancel", 5, "class").lecturer().meeting().thread("T").invitation("cancelled")).card("again");

        assertThat(List.of(card.cancelled(), card.joinable())).containsExactly(false, true);
    }

    @Test
    void aDeadlinesTimeDecidesWhenItPasses() {
        assertThat(deadline("opens", 0, null, null).at()).isEqualTo(TODAY.atStartOfDay());
        assertThat(deadline("register", 0, null, null).at()).isEqualTo(TODAY.plusDays(1).atStartOfDay());
        assertThat(deadline("due", 0, "08:00", null).passed(NOW_IN_VIETNAM)).isTrue();
        assertThat(deadline("due", 0, "08:01", null).passed(NOW_IN_VIETNAM)).isFalse();
        assertThat(new Period(LocalDate.of(2026, 9, 28), LocalDate.of(2026, 9, 30), "all_day", null, null, false, null)
                .endAt()).isEqualTo(LocalDate.of(2026, 10, 1).atStartOfDay());
    }
}
