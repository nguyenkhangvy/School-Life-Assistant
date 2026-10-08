package vn.edu.hcmiu.sla.school.pages;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.flash;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.List;

import jakarta.persistence.EntityManager;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.core.Flash;
import vn.edu.hcmiu.sla.school.SchoolTestData;
import vn.edu.hcmiu.sla.school.SchoolTestData.Meeting;
import vn.edu.hcmiu.sla.school.TestClock;
import vn.edu.hcmiu.sla.school.model.SchoolMail;
import vn.edu.hcmiu.sla.school.model.SchoolMailAddedPeriod;
import vn.edu.hcmiu.sla.school.model.SchoolMailAddedPeriodRepository;
import vn.edu.hcmiu.sla.school.model.SchoolMailDeadline;
import vn.edu.hcmiu.sla.school.model.SchoolMailJoined;
import vn.edu.hcmiu.sla.school.model.SchoolMailJoinedRepository;
import vn.edu.hcmiu.sla.school.model.SchoolMailPeriod;
import vn.edu.hcmiu.sla.school.model.SchoolMailSession;
import vn.edu.hcmiu.sla.school.model.SchoolMailStatus;

/**
 * Mailbox and Join… with what the laptop now finds in an email: each session's check-in, mode, link, end and label,
 * Periods (Add, Remove), every deadline as tags, the registered flag, lecturers' meetings and cancelled Outlook
 * invitations (spec 2026-10-07-mail-event-kinds-design.md, 6.2, 6.3 and 6.6).
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@Import(TestClock.Config.class)
class MailEventKindsPageTest {

    static final LocalDateTime NOW = LocalDateTime.of(2026, 9, 28, 1, 0); // Mon 28/09 08:00 in Vietnam
    static final LocalDate TUE = LocalDate.of(2026, 9, 29);
    static final String CONTEST = "a".repeat(64);
    static final String FAIR = "b".repeat(64);
    static final String MEETING = "c".repeat(64);
    static final String REQUEST = "d".repeat(64);
    static final String CANCELLED = "e".repeat(64);
    static final String THANKS = "1".repeat(64);
    static final String GONE = "f".repeat(64);
    static final String OPENING = "2026-11-02/2026-11-05/daily_window/09:00";
    static final String FAIR_DAYS = "2026-10-03/2026-10-04/all_day/-";

    @Autowired
    MockMvc mvc;

    @Autowired
    EntityManager db;

    @Autowired
    TestClock clock;

    @Autowired
    SchoolMailJoinedRepository joined;

    @Autowired
    SchoolMailAddedPeriodRepository added;

    SchoolTestData data;
    AppUser an;

    @BeforeEach
    void anInboxAndATimetable() {
        data = new SchoolTestData(db);
        an = data.user("an@example.com");
        clock.set(NOW);
        inbox(an);
        // Tue 29/09 13:00-15:30
        data.course(an, "IT093IU", "Web Application Development",
                new Meeting(LocalDateTime.of(2026, 9, 29, 6, 0), LocalDateTime.of(2026, 9, 29, 8, 30), "A2.401"));
    }

    @AfterEach
    void realTime() {
        clock.reset();
    }

    SchoolMail mail(AppUser who, String key, String thread, int hoursAgo, String subject, List<String> categories,
            boolean lecturer) {
        SchoolMail mail = new SchoolMail(who.id(), key, "00A1" + key.substring(0, 4).toUpperCase(), thread,
                NOW.minusHours(hoursAgo), lecturer ? "Tran Van An" : "Đoàn Hội",
                lecturer ? "tvan@hcmiu.edu.vn" : "doanhoi@hcmiu.edu.vn", subject, categories, lecturer, List.of(), true,
                null);
        db.persist(mail);
        return mail;
    }

    static LocalTime at(String time) {
        return time == null ? null : LocalTime.parse(time);
    }

    void inbox(AppUser who) {
        SchoolMail contest = mail(who, CONTEST, null, 3, "[THƯ MỜI] Cuộc thi Ý tưởng khởi nghiệp", List.of("event"),
                false);
        contest.getSessions().add(new SchoolMailSession(contest, TUE, at("15:45"), at("17:00"), false, false,
                at("15:00"), null, "in_person", null, "round_1"));
        contest.getSessions().add(new SchoolMailSession(contest, LocalDate.of(2026, 12, 31), at("22:00"), at("00:30"),
                false, true, null, at("21:45"), "online", null, "final"));
        contest.getPeriods().add(new SchoolMailPeriod(contest, LocalDate.of(2026, 11, 2), LocalDate.of(2026, 11, 5),
                "daily_window", at("09:00"), at("17:00"), false, "opening"));
        contest.getPeriods().add(new SchoolMailPeriod(contest, LocalDate.of(2026, 10, 26), LocalDate.of(2026, 10, 30),
                "all_day", null, null, true, null));
        contest.getDeadlines().add(new SchoolMailDeadline(contest, "register", LocalDate.of(2026, 9, 28), at("07:00"),
                "in_person"));
        contest.getDeadlines().add(new SchoolMailDeadline(contest, "register", LocalDate.of(2026, 10, 1), at("17:00"),
                "online"));
        contest.getDeadlines().add(new SchoolMailDeadline(contest, "confirm", LocalDate.of(2026, 10, 15), null, null));
        contest.getDeadlines().add(new SchoolMailDeadline(contest, "due", LocalDate.of(2026, 10, 18), at("23:59"),
                null));
        SchoolMail fair = mail(who, FAIR, null, 4, "Ngày hội việc làm", List.of("event"), false);
        fair.getPeriods().add(new SchoolMailPeriod(fair, LocalDate.of(2026, 10, 3), LocalDate.of(2026, 10, 4),
                "all_day", null, null, false, null));
        SchoolMail meeting = mail(who, MEETING, null, 5, "Họp nhóm đồ án", List.of("class"), true);
        meeting.setFlags(true, false, null);
        meeting.getSessions().add(new SchoolMailSession(meeting, TUE.plusDays(1), at("09:00"), at("10:00")));
        SchoolMail request = mail(who, REQUEST, "T", 6, "Tư vấn học tập", List.of("class"), true);
        request.setFlags(true, false, "request");
        request.getSessions().add(new SchoolMailSession(request, TUE.plusDays(2), at("09:00"), at("10:00")));
        SchoolMail cancelled = mail(who, CANCELLED, "T", 2, "Đã hủy: Tư vấn học tập", List.of("class"), true);
        cancelled.setFlags(true, false, "cancelled");
        SchoolMail thanks = mail(who, THANKS, null, 1, "[THƯ MỜI] Cảm ơn bạn đã đăng ký Hội thảo AI", List.of("event"),
                false);
        thanks.setFlags(false, true, null);
        thanks.getSessions().add(new SchoolMailSession(thanks, TUE.plusDays(3), at("08:00"), at("11:00")));
        thanks.getDeadlines().add(new SchoolMailDeadline(thanks, "register", LocalDate.of(2026, 9, 26), null, null));
        db.persist(new SchoolMailStatus(who.id(), LocalDate.of(2026, 8, 1), true, NOW.minusHours(1)));
        db.flush();
    }

    String html(MockHttpServletRequestBuilder request) throws Exception {
        return mvc.perform(request.with(user(an))).andExpect(status().isOk()).andReturn().getResponse()
                .getContentAsString();
    }

    String page() throws Exception {
        return html(get("/school/mailbox"));
    }

    /** The HTML of one card's row, each run of spaces and line breaks as one space. */
    static String row(String html, String key) {
        int start = html.indexOf("id=\"mail-" + key + "\"");
        int end = html.indexOf("</li>", start);
        return html.substring(start, end).replaceAll("\\s+", " ");
    }

    MockHttpServletRequestBuilder save(String key) {
        return post("/school/mailbox/" + key + "/join").with(user(an)).with(csrf());
    }

    List<String> addedRows() {
        return added.findAll().stream().map(p -> p.getMailKey().substring(0, 1) + " " + p.getFirstDay() + "→"
                + p.getLastDay() + " " + p.getMode() + " " + p.getFromTime() + "-" + p.getToTime() + " " + p.getLabel()
                + " " + p.getTitle()).toList();
    }

    SchoolMailAddedPeriod addedRow(String key, int firstDay, int lastDay) {
        return new SchoolMailAddedPeriod(an.id(), key, TUE.plusDays(firstDay), TUE.plusDays(lastDay), "all_day", null,
                null, false, null, "Ngày hội việc làm", NOW);
    }

    // ---- the row ------------------------------------------------------------------------------------------------

    @Test
    void theRowShowsEveryDeadlineAndEachSessionsDetails() throws Exception {
        String contest = row(page(), CONTEST);

        assertThat(contest).contains("<span class=\"tag tag-register\">Register by: <s>In person 07:00 Mon 28/09</s>"
                + " · Online 17:00 Thu 01/10</span>")
                .contains("<span class=\"tag tag-confirm\">Confirm by Thu 15/10</span>")
                .contains("<span class=\"tag tag-due\">Due 23:59 Sun 18/10</span>")
                .contains("Tue 29/09 15:45–17:00 · check-in 15:00 · In person · Round 1")
                .contains("Thu 31/12 22:00 – Fri 01/01 00:30 · Online · link from 21:45 · Final");
    }

    @Test
    void aSessionClashesFromItsCheckIn() throws Exception {
        // The class ends at 15:30: the programme (15:45) is free, but the check-in (15:00) isn't.
        String contest = row(page(), CONTEST);

        assertThat(contest.substring(contest.indexOf("Tue 29/09 15:45"))).startsWith(
                "Tue 29/09 15:45–17:00 · check-in 15:00 · In person · Round 1"
                        + " <span class=\"mark mark-conflict\">⚠ Conflict: Web Application Development</span>");
    }

    @Test
    void theRowListsPeriodsAndACardWithOnlyOneOffersAdd() throws Exception {
        String html = page();

        assertThat(row(html, CONTEST)).contains("Period · Mon 02/11 → Thu 05/11 · 09:00–17:00 each day · Opening")
                .contains("Period · Mon 26/10 → Fri 30/10 · all day · your own time comes later")
                .doesNotContain("add-period");
        assertThat(row(html, FAIR)).contains("Period · Sat 03/10 → Sun 04/10 · all day")
                .contains("action=\"/school/mailbox/" + FAIR + "/add-period\"")
                .contains("href=\"/school/mailbox/" + FAIR + "/join\">Join…</a>");
    }

    @Test
    void aLecturersMeetingCanBeJoined() throws Exception {
        String meeting = row(MailboxPageTest.box(page(), "lecturers"), MEETING);

        assertThat(meeting).contains("Wed 30/09 09:00–10:00").contains("✓ No conflict")
                .contains("href=\"/school/mailbox/" + MEETING + "/join\">Join…</a>");
    }

    @Test
    void aCancelledMeetingIsStruckOutAndCantBeJoined() throws Exception {
        String cancelled = row(page(), CANCELLED);

        assertThat(cancelled).contains("<span class=\"tag tag-cancelled\">Cancelled</span>")
                .contains("<s>Thu 01/10 09:00–10:00</s>").doesNotContain("Join…").doesNotContain("No conflict");
        mvc.perform(get("/school/mailbox/" + CANCELLED + "/join").with(user(an))).andExpect(status().isNotFound());
    }

    @Test
    void aJoinedSessionOfACancelledMeetingStaysUntilLeft() throws Exception {
        db.persist(new SchoolMailJoined(an.id(), REQUEST, TUE.plusDays(2), at("09:00"), at("10:00"), "Tư vấn học tập",
                null, false, false, NOW));
        db.flush();

        assertThat(row(page(), CANCELLED)).contains("Thu 01/10 09:00–10:00 <span class=\"mark mark-joined\">Joined");
        assertThat(html(get("/school/mailbox/" + CANCELLED + "/join"))).contains("This meeting was cancelled")
                .contains("Leave event");

        mvc.perform(post("/school/mailbox/" + CANCELLED + "/leave").with(user(an)).with(csrf()))
                .andExpect(redirectedUrl("/school/mailbox#mail-" + CANCELLED));
        assertThat(joined.count()).isZero();
    }

    @Test
    void aRegisteredCardSaysSoAndStaysAhead() throws Exception {
        String html = page();

        assertThat(row(html, THANKS)).contains("<span class=\"tag tag-registered\">Registered ✓</span>")
                .doesNotContain("Registration closed").doesNotContain("tag-register\"");
        String events = MailboxPageTest.box(html, "events");
        int past = events.indexOf("<details");
        assertThat(events.substring(0, past < 0 ? events.length() : past)).contains("id=\"mail-" + THANKS + "\"");
    }

    // ---- Add and Remove -----------------------------------------------------------------------------------------

    @Test
    void addPutsTheOnlyPeriodInTheTimetableAndRemoveTakesItOut() throws Exception {
        mvc.perform(post("/school/mailbox/" + FAIR + "/add-period").with(user(an)).with(csrf()))
                .andExpect(redirectedUrl("/school/mailbox#mail-" + FAIR));

        assertThat(addedRows()).containsExactly("b 2026-10-03→2026-10-04 all_day null-null null Ngày hội việc làm");
        String fair = row(page(), FAIR);
        assertThat(fair).contains("<span class=\"mark mark-joined\">Added ✓</span>")
                .contains("<input type=\"hidden\" name=\"period\" value=\"" + FAIR_DAYS + "\">")
                .doesNotContain("add-period");

        mvc.perform(post("/school/mailbox/" + FAIR + "/remove-period").with(user(an)).with(csrf())
                .param("period", FAIR_DAYS)).andExpect(redirectedUrl("/school/mailbox#mail-" + FAIR));
        assertThat(added.count()).isZero();
    }

    @Test
    void addingTwiceKeepsOneCopy() throws Exception {
        for (int i = 0; i < 2; i++) {
            mvc.perform(post("/school/mailbox/" + FAIR + "/add-period").with(user(an)).with(csrf()));
        }

        assertThat(added.count()).isEqualTo(1);
    }

    @Test
    void aPeriodThatEndedCantBeAdded() throws Exception {
        clock.set(LocalDateTime.of(2026, 10, 4, 18, 0)); // Mon 05/10 01:00 in Vietnam

        mvc.perform(post("/school/mailbox/" + FAIR + "/add-period").with(user(an)).with(csrf()))
                .andExpect(redirectedUrl("/school/mailbox#mail-" + FAIR))
                .andExpect(flash().attribute("flashes", List.of(new Flash("error", MailboxController.PERIOD_OVER))));

        assertThat(added.count()).isZero();
    }

    @Test
    void oneEmailHasAtMostFiveAddedPeriods() throws Exception {
        for (int week = 1; week <= 5; week++) {
            db.persist(addedRow(FAIR, 7 * week, 7 * week + 1));
        }
        db.flush();

        mvc.perform(post("/school/mailbox/" + FAIR + "/add-period").with(user(an)).with(csrf()))
                .andExpect(flash().attribute("flashes", List.of(new Flash("error",
                        MailboxController.TOO_MANY_PERIODS))));

        assertThat(added.count()).isEqualTo(5);
    }

    @Test
    void addAndRemoveNeedTheSecurityCodeAndTheStudentsOwnCard() throws Exception {
        AppUser binh = data.user("binh@example.com");
        db.persist(addedRow(FAIR, 4, 5));
        db.flush();

        mvc.perform(post("/school/mailbox/" + FAIR + "/add-period").with(user(an))).andExpect(status().isForbidden());
        mvc.perform(post("/school/mailbox/" + FAIR + "/add-period").with(user(binh)).with(csrf()))
                .andExpect(status().isNotFound());
        mvc.perform(post("/school/mailbox/" + FAIR + "/remove-period").with(user(binh)).with(csrf())
                .param("period", "2026-10-03/2026-10-04/all_day/-")).andExpect(status().isNotFound());
        mvc.perform(post("/school/mailbox/" + MEETING + "/add-period").with(user(an)).with(csrf()))
                .andExpect(redirectedUrl("/school/mailbox#mail-" + MEETING));
        assertThat(added.count()).isEqualTo(1);
    }

    @Test
    void anAddedPeriodWhoseEmailIsGoneCanStillBeLeft() throws Exception {
        db.persist(new SchoolMailAddedPeriod(an.id(), GONE, TUE.plusDays(6), TUE.plusDays(8), "daily_window",
                at("09:00"), at("17:00"), false, null, "Hội chợ sách", NOW));
        db.flush();

        String gone = MailboxPageTest.box(page(), "gone");
        assertThat(gone).contains("Hội chợ sách").contains("Next: Mon 05/10")
                .contains("Period · Mon 05/10 → Wed 07/10 · 09:00–17:00 each day")
                .contains("action=\"/school/mailbox/" + GONE + "/leave\"");

        mvc.perform(post("/school/mailbox/" + GONE + "/leave").with(user(an)).with(csrf()))
                .andExpect(redirectedUrl("/school/mailbox"));
        assertThat(added.count()).isZero();
        mvc.perform(post("/school/mailbox/" + GONE + "/leave").with(user(an)).with(csrf()))
                .andExpect(status().isNotFound());
    }

    // ---- Join… --------------------------------------------------------------------------------------------------

    @Test
    void theJoinPageListsPeriodsAndTheDeadlines() throws Exception {
        String html = html(get("/school/mailbox/" + CONTEST + "/join"));

        assertThat(html).contains("<legend>Periods: come at any time</legend>")
                .contains("name=\"periods\" value=\"" + OPENING + "\"")
                .contains("<s>Register by 07:00 Mon 28/09 · In person</s>")
                .contains("Register by 17:00 Thu 01/10 · Online").contains("Confirm by Thu 15/10")
                .contains("Due 23:59 Sun 18/10").contains("Add to my Timetable");
    }

    @Test
    void savingAddsTheTickedPeriodsAndJoinedCopiesKeepTheirDetails() throws Exception {
        mvc.perform(save(CONTEST).param("sessions", "2026-09-29T15:45", "2026-12-31T22:00").param("periods", OPENING))
                .andExpect(redirectedUrl("/school/mailbox#mail-" + CONTEST));

        assertThat(addedRows()).containsExactly(
                "a 2026-11-02→2026-11-05 daily_window 09:00-17:00 opening [THƯ MỜI] Cuộc thi Ý tưởng khởi nghiệp");
        assertThat(joined.findAll()).extracting(j -> j.getDay() + " " + j.getStart() + "-" + j.getEnd() + " in "
                + j.getCheckIn() + " " + j.getMode() + " +" + j.isEndsNextDay())
                .containsExactlyInAnyOrder("2026-09-29 15:45-17:00 in 15:00 in_person +false",
                        "2026-12-31 22:00-00:30 in null online +true");
        assertThat(html(get("/school/mailbox/" + CONTEST + "/join")))
                .contains("value=\"" + OPENING + "\" checked=\"checked\"");

        mvc.perform(save(CONTEST).param("sessions", "2026-09-29T15:45"));
        assertThat(added.count()).isZero();
    }

    @Test
    void aPeriodThatEndedOrIsUnknownIsRefusedWithAMessage() throws Exception {
        String html = mvc.perform(save(CONTEST).param("periods", "2026-09-01/2026-09-05/all_day/-"))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();

        assertThat(html).contains(MailboxController.PERIOD_OVER);
        assertThat(added.count()).isZero();
    }

    @Test
    void theFivePeriodLimitCountsPeriodsAlreadyOver() throws Exception {
        for (int week = 1; week <= 4; week++) {
            db.persist(new SchoolMailAddedPeriod(an.id(), CONTEST, TUE.minusDays(7 * week), TUE.minusDays(7 * week),
                    "all_day", null, null, false, null, "Cuộc thi", NOW));
        }
        db.flush();

        String html = mvc.perform(save(CONTEST).param("periods", OPENING, "2026-10-26/2026-10-30/all_day/-"))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();

        assertThat(html).contains(MailboxController.TOO_MANY_PERIODS);
        assertThat(added.count()).isEqualTo(4);
    }

    @Test
    void leavingRemovesAddedPeriodsAheadButKeepsThoseOver() throws Exception {
        db.persist(new SchoolMailAddedPeriod(an.id(), CONTEST, TUE.minusDays(9), TUE.minusDays(8), "all_day", null,
                null, false, null, "Cuộc thi", NOW));
        db.flush();
        mvc.perform(save(CONTEST).param("periods", OPENING));

        mvc.perform(post("/school/mailbox/" + CONTEST + "/leave").with(user(an)).with(csrf()))
                .andExpect(redirectedUrl("/school/mailbox#mail-" + CONTEST));

        assertThat(added.findAll()).extracting(SchoolMailAddedPeriod::getFirstDay).containsExactly(TUE.minusDays(9));
    }
}
