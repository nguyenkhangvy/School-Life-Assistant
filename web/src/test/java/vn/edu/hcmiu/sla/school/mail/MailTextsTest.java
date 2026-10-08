package vn.edu.hcmiu.sla.school.mail;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import java.time.LocalTime;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import vn.edu.hcmiu.sla.school.mail.Mailbox.Deadline;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Period;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Session;

/** How sessions, Periods, deadlines and the laptop's codes read (spec 2026-10-07-mail-event-kinds-design.md, 6.2). */
class MailTextsTest {

    static final LocalDate THU = LocalDate.of(2026, 12, 31);

    static LocalTime at(String time) {
        return time == null ? null : LocalTime.parse(time);
    }

    static Session session(String start, String end, boolean approximate, boolean nextDay, String checkIn,
            String link, String mode, String relative, String label) {
        return new Session(THU, at(start), at(end), approximate, nextDay, at(checkIn), at(link), mode, relative, label);
    }

    @Test
    void aSessionSaysWhatTheEmailGaveAndNothingElse() {
        assertThat(MailTexts.session(new Session(THU, at("13:00"), at("14:00")))).isEqualTo("Thu 31/12 13:00–14:00");
        assertThat(MailTexts.session(new Session(THU, at("14:00"), null))).isEqualTo("Thu 31/12 from 14:00");
    }

    @Test
    void aSessionAddsItsCheckInModeLinkRelativeDayAndLabel() {
        assertThat(MailTexts.session(session("13:30", "15:30", true, false, "13:00", null, "in_person", null,
                "round_1"))).isEqualTo("Thu 31/12 13:30–~15:30 · check-in 13:00 · In person · Round 1");
        assertThat(MailTexts.session(session("09:30", null, false, false, null, "09:00", "online", "tomorrow", null)))
                .isEqualTo("Thu 31/12 from 09:30 · Online · link from 09:00 · from 'tomorrow'");
    }

    @Test
    void aSessionThatEndsTheNextDaySaysBothDays() {
        assertThat(MailTexts.session(session("22:00", "00:30", false, true, null, null, null, null, "final")))
                .isEqualTo("Thu 31/12 22:00 – Fri 01/01 00:30 · Final");
        assertThat(MailTexts.session(session("22:00", "00:30", true, true, null, null, null, null, null)))
                .isEqualTo("Thu 31/12 22:00 – Fri 01/01 ~00:30");
    }

    @ParameterizedTest
    @CsvSource({
        "today, today", "tomorrow, tomorrow", "day_after_tomorrow, the day after tomorrow",
        "this_week, this Thursday", "next_week, next Thursday", "weekday, Thursday", "yesterday,"})
    void aRelativeDayReadsAsTheWordItCameFrom(String code, String text) {
        assertThat(MailTexts.relative(code, THU)).isEqualTo(text);
    }

    @ParameterizedTest
    @CsvSource({
        "round_3, Round 3", "shift_2, Shift 2", "preliminary, Preliminary round", "qualifying, Qualifying round",
        "semifinal, Semi-final", "final, Final", "opening, Opening", "closing, Closing", "round_9,"})
    void labelsComeFromTheSitesOwnList(String code, String text) {
        assertThat(MailTexts.label(code)).isEqualTo(text);
    }

    static Period period(String first, String last, String mode, String from, String to) {
        return new Period(LocalDate.parse(first), LocalDate.parse(last), mode, at(from), at(to), false, null);
    }

    @Test
    void eachKindOfPeriodReadsItsOwnWay() {
        assertThat(MailTexts.period(period("2026-11-02", "2026-11-05", "daily_window", "09:00", "17:00")))
                .isEqualTo("Period · Mon 02/11 → Thu 05/11 · 09:00–17:00 each day");
        assertThat(MailTexts.period(period("2026-10-26", "2026-10-30", "all_day", null, null)))
                .isEqualTo("Period · Mon 26/10 → Fri 30/10 · all day");
        assertThat(MailTexts.period(period("2026-11-28", "2026-11-29", "one_window", "09:00", "16:00")))
                .isEqualTo("Period · Sat 28/11 09:00 → Sun 29/11 16:00");
        assertThat(MailTexts.period(period("2026-11-14", "2026-11-14", "one_window", "08:00", "16:00")))
                .isEqualTo("Period · Sat 14/11 · 08:00–16:00");
        assertThat(MailTexts.period(period("2026-10-20", "2026-10-20", "all_day", null, null)))
                .isEqualTo("Period · Tue 20/10 · all day");
    }

    @Test
    void aPeriodSaysWhenTheStudentsOwnTimeComesLaterAndItsLabel() {
        assertThat(MailTexts.period(new Period(LocalDate.of(2026, 11, 18), LocalDate.of(2026, 11, 18), "one_window",
                at("09:00"), at("16:00"), true, "shift_1")))
                .isEqualTo("Period · Wed 18/11 · 09:00–16:00 · your own time comes later · Shift 1");
    }

    @Test
    void anAddedPeriodsHoursOnTheTimetable() {
        assertThat(MailTexts.periodHours(period("2026-11-02", "2026-11-05", "daily_window", "09:00", "17:00")))
                .isEqualTo("09:00–17:00 each day");
        assertThat(MailTexts.periodHours(period("2026-11-28", "2026-11-29", "one_window", "09:00", "16:00")))
                .isEqualTo("09:00 Sat until 16:00 Sun");
        assertThat(MailTexts.periodHours(period("2026-11-14", "2026-11-14", "one_window", "08:00", "16:00")))
                .isEqualTo("08:00–16:00");
        assertThat(MailTexts.periodHours(period("2026-10-26", "2026-10-30", "all_day", null, null))).isNull();
    }

    @Test
    void eachDeadlineReadsAsWhatItAsks() {
        assertThat(new Deadline("opens", LocalDate.of(2026, 10, 8), at("08:00"), null).text())
                .isEqualTo("Registration opens 08:00 Thu 08/10");
        assertThat(new Deadline("register", LocalDate.of(2026, 10, 10), null, "in_person").text())
                .isEqualTo("Register by Sat 10/10 · In person");
        assertThat(new Deadline("confirm", LocalDate.of(2026, 10, 15), null, null).text())
                .isEqualTo("Confirm by Thu 15/10");
        assertThat(new Deadline("due", LocalDate.of(2026, 10, 18), at("23:59"), "online").text())
                .isEqualTo("Due 23:59 Sun 18/10 · Online");
    }
}
