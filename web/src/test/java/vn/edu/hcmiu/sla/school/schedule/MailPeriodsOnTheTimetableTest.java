package vn.edu.hcmiu.sla.school.schedule;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.List;
import java.util.Map;

import jakarta.persistence.EntityManager;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import vn.edu.hcmiu.sla.auth.AppUser;
import vn.edu.hcmiu.sla.school.SchoolTestData;
import vn.edu.hcmiu.sla.school.SchoolTestData.Meeting;
import vn.edu.hcmiu.sla.school.TestClock;
import vn.edu.hcmiu.sla.school.model.SchoolMail;
import vn.edu.hcmiu.sla.school.model.SchoolMailAddedPeriod;
import vn.edu.hcmiu.sla.school.model.SchoolMailChoice;
import vn.edu.hcmiu.sla.school.model.SchoolMailJoined;

/**
 * Joined sessions with a check-in or an end on the next day, and added Periods, on the Timetable's calendar feed and
 * Overview's Today and Tomorrow (spec 2026-10-07-mail-event-kinds-design.md, 6.4 and 6.5). Rows are UTC; the feed
 * shows Vietnam time.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@Import(TestClock.Config.class)
class MailPeriodsOnTheTimetableTest {

    static final JsonMapper JSON = JsonMapper.builder().build();
    static final LocalDateTime NOW = LocalDateTime.of(2026, 9, 28, 1, 0); // Mon 28/09 08:00 in Vietnam
    static final String FAIR = "b".repeat(64);
    static final String TALK = "a".repeat(64);

    @Autowired
    MockMvc mvc;

    @Autowired
    EntityManager db;

    @Autowired
    TestClock clock;

    SchoolTestData data;
    AppUser an;

    @BeforeEach
    void anAccount() {
        data = new SchoolTestData(db);
        an = data.user("an@example.com");
        clock.set(NOW);
    }

    @AfterEach
    void realTime() {
        clock.reset();
    }

    List<Map<String, Object>> feed(String start, String end) throws Exception {
        String body = mvc.perform(get("/school/api/calendar").param("start", start).param("end", end).with(user(an)))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        return JSON.readValue(body, new TypeReference<List<Map<String, Object>>>() {
        });
    }

    List<Map<String, Object>> week() throws Exception {
        return feed("2026-09-28T00:00:00Z", "2026-10-05T00:00:00Z");
    }

    SchoolMailAddedPeriod added(String key, LocalDate first, LocalDate last, String mode, String from, String to,
            String label) {
        SchoolMailAddedPeriod row = new SchoolMailAddedPeriod(an.id(), key, first, last, mode,
                from == null ? null : LocalTime.parse(from), to == null ? null : LocalTime.parse(to), false, label,
                "Ngày hội việc làm IU", NOW);
        db.persist(row);
        db.flush();
        return row;
    }

    SchoolMail mail(String key, String subject) {
        SchoolMail mail = new SchoolMail(an.id(), key, "00A1" + key.substring(0, 4).toUpperCase(), null,
                NOW.minusDays(1), "P.CTSV [OSS]", "oss@hcmiu.edu.vn", subject, List.of("event"), false, List.of(), true,
                null);
        db.persist(mail);
        db.flush();
        return mail;
    }

    @Test
    void aJoinedSessionStartsAtItsCheckInAndSaysSo() throws Exception {
        db.persist(new SchoolMailJoined(an.id(), TALK, LocalDate.of(2026, 9, 29), LocalTime.of(14, 0),
                LocalTime.of(16, 30), "Workshop", "Hall A2", false, false, NOW)
                .keeping(LocalTime.of(13, 30), "in_person", false, false));
        db.flush();

        assertThat(week()).singleElement().satisfies(event -> assertThat(List.of(event.get("title"), event.get("start"),
                event.get("end"))).containsExactly("Event: Workshop · check-in 13:30", "2026-09-29T13:30:00",
                        "2026-09-29T16:30:00"));
    }

    @Test
    void aJoinedSessionThatEndsTheNextDayRunsPastMidnight() throws Exception {
        db.persist(new SchoolMailJoined(an.id(), TALK, LocalDate.of(2026, 10, 3), LocalTime.of(22, 0),
                LocalTime.of(0, 30), "Countdown", null, false, false, NOW).keeping(null, "online", true, true));
        db.flush();

        assertThat(week()).singleElement().satisfies(event -> assertThat(List.of(event.get("start"), event.get("end")))
                .containsExactly("2026-10-03T22:00:00", "2026-10-04T00:30:00"));
    }

    @Test
    void anAddedPeriodIsABarOverItsDaysWithItsLabelAndHours() throws Exception {
        added(FAIR, LocalDate.of(2026, 9, 30), LocalDate.of(2026, 10, 2), "daily_window", "09:00", "17:00", "opening");
        added(TALK, LocalDate.of(2026, 10, 3), LocalDate.of(2026, 10, 4), "one_window", "09:00", "16:00", null);

        assertThat(week()).extracting(event -> List.of(event.get("title"), event.get("start"), event.get("end"),
                event.get("allDay"), event.get("classNames"), event.get("url")))
                .containsExactly(
                        List.of("Period: Opening · Ngày hội việc làm IU · 09:00–17:00 each day", "2026-09-30",
                                "2026-10-03", true, List.of("event-period"), "/school/mailbox#mail-" + FAIR),
                        List.of("Period: Ngày hội việc làm IU · 09:00 Sat until 16:00 Sun", "2026-10-03", "2026-10-05",
                                true, List.of("event-period"), "/school/mailbox#mail-" + TALK));
    }

    @Test
    void aPeriodThatStartedBeforeTheWeekStillShows() throws Exception {
        added(FAIR, LocalDate.of(2026, 9, 20), LocalDate.of(2026, 9, 29), "all_day", null, null, null);
        added(TALK, LocalDate.of(2026, 9, 10), LocalDate.of(2026, 9, 27), "all_day", null, null, null);

        assertThat(week()).extracting(event -> event.get("start")).containsExactly("2026-09-20");
    }

    @Test
    void aPeriodIsHiddenWhileItsCardIsDone() throws Exception {
        mail(FAIR, "Ngày hội việc làm IU");
        added(FAIR, LocalDate.of(2026, 9, 30), LocalDate.of(2026, 10, 2), "all_day", null, null, null);
        SchoolMailChoice choice = new SchoolMailChoice(an.id(), FAIR, NOW);
        choice.setDone(true, NOW);
        db.persist(choice);
        db.flush();

        assertThat(week()).isEmpty();

        choice.setDone(false, NOW);
        db.flush();
        assertThat(week()).hasSize(1);
    }

    @Test
    void periodsAreNeverBusy() throws Exception {
        // An own event during a Period doesn't clash with it: no ⚠ on either.
        added(FAIR, LocalDate.of(2026, 9, 29), LocalDate.of(2026, 9, 29), "one_window", "08:00", "17:00", null);
        data.myEvent(an, "Tự học", LocalDate.of(2026, 9, 29), LocalDate.of(2026, 9, 29), LocalTime.of(9, 0),
                LocalTime.of(10, 0));

        assertThat(week()).extracting(event -> event.get("title"))
                .containsExactlyInAnyOrder("Period: Ngày hội việc làm IU · 08:00–17:00", "My event: Tự học");
    }

    @Test
    void anotherStudentsPeriodsAreNeverInMyCalendar() throws Exception {
        AppUser binh = data.user("binh@example.com");
        db.persist(new SchoolMailAddedPeriod(binh.id(), FAIR, LocalDate.of(2026, 9, 30), LocalDate.of(2026, 10, 2),
                "all_day", null, null, false, null, "Ngày hội", NOW));
        db.flush();

        assertThat(week()).isEmpty();
    }

    @Test
    void theOverviewListsThePeriodsRunningTodayAndTomorrow() throws Exception {
        added(FAIR, LocalDate.of(2026, 9, 26), LocalDate.of(2026, 9, 28), "all_day", null, null, null);
        added(TALK, LocalDate.of(2026, 9, 29), LocalDate.of(2026, 9, 30), "daily_window", "13:00", "16:00", "shift_1");
        // Tue 29/09 08:00-10:30 in Vietnam
        data.course(an, "IT093IU", "Web Application Development",
                new Meeting(LocalDateTime.of(2026, 9, 29, 1, 0), LocalDateTime.of(2026, 9, 29, 3, 30), "A2.508"));

        String html = mvc.perform(get("/school").with(user(an))).andExpect(status().isOk()).andReturn().getResponse()
                .getContentAsString();

        String today = html.substring(html.indexOf("data-live=\"today\""), html.indexOf("data-live=\"tomorrow\""));
        String tomorrow = html.substring(html.indexOf("data-live=\"tomorrow\""), html.indexOf("Open the calendar"));
        assertThat(today).contains("<strong>Period:</strong> Ngày hội việc làm IU").contains("All day")
                .contains("href=\"/school/mailbox#mail-" + FAIR + "\"").doesNotContain("No classes or exams today");
        assertThat(tomorrow).contains("<strong>Period:</strong> Shift 1 · Ngày hội việc làm IU · 13:00–16:00 each day")
                .contains("Web Application Development");
        assertThat(tomorrow.indexOf("Period:")).isLessThan(tomorrow.indexOf("Web Application Development"));
    }
}
