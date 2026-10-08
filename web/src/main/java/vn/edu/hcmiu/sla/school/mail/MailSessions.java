package vn.edu.hcmiu.sla.school.mail;

import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.school.VietnamTime;
import vn.edu.hcmiu.sla.school.mail.Conflicts.Busy;
import vn.edu.hcmiu.sla.school.mail.Conflicts.Mark;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Card;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Period;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Session;
import vn.edu.hcmiu.sla.school.model.SchoolMailAddedPeriod;
import vn.edu.hcmiu.sla.school.model.SchoolMailAddedPeriodRepository;
import vn.edu.hcmiu.sla.school.model.SchoolMailJoined;
import vn.edu.hcmiu.sla.school.model.SchoolMailJoinedRepository;
import vn.edu.hcmiu.sla.school.schedule.Schedule;
import vn.edu.hcmiu.sla.school.schedule.Schedule.Item;

/**
 * The sessions and Periods shown under an event's row and on its Join page: the ones the laptop found and the ones
 * the student joined or added, each session marked Conflict / No conflict against the timetable
 * (docs/superpowers/specs/2026-09-28-mailbox-events-design.md, sections 4.2, 4.5 and 4.6, and
 * 2026-10-07-mail-event-kinds-design.md, sections 6.2–6.4). Periods are never busy and have no mark.
 */
@Service
public class MailSessions {

    static final Duration EXAM_WITHOUT_LENGTH = Duration.ofMinutes(90);
    private static final DateTimeFormatter CLOCK = DateTimeFormatter.ofPattern("HH:mm");

    /** One session of a card: found in its email and/or joined, with its mark. */
    public record Line(Session session, boolean found, boolean joined, Mark mark) {

        /** "Tue 29/09 13:00–14:00 · check-in 12:45 · Online", or "Thu 01/10 from 14:00" without an end (MailTexts). */
        public String when() {
            return MailTexts.session(session);
        }

        /** How the Join form names it: "2026-09-29T13:30". */
        public String id() {
            return session.day() + "T" + CLOCK.format(session.start());
        }
    }

    /** One Period of a card: found in its email and/or added to the Timetable by the student. */
    public record PeriodLine(Period period, boolean found, boolean added) {

        /** "Period · Mon 02/11 → Thu 05/11 · 09:00–17:00 each day" (MailTexts). */
        public String text() {
            return MailTexts.period(period);
        }

        /** How the Join form and Add and Remove name it. */
        public String id() {
            return period.id();
        }
    }

    private final Schedule schedule;
    private final SchoolMailJoinedRepository joined;
    private final SchoolMailAddedPeriodRepository added;

    public MailSessions(Schedule schedule, SchoolMailJoinedRepository joined, SchoolMailAddedPeriodRepository added) {
        this.schedule = schedule;
        this.joined = joined;
        this.added = added;
    }

    static Session session(SchoolMailJoined row) {
        return new Session(row.getDay(), row.getStart(), row.getEnd(), row.isEndIsApproximate(), row.isEndsNextDay(),
                row.getCheckIn(), null, row.getMode(), null, null);
    }

    public static Period period(SchoolMailAddedPeriod row) {
        return new Period(row.getFirstDay(), row.getLastDay(), row.getMode(), row.getFromTime(), row.getToTime(),
                row.isDetailsLater(), row.getLabel());
    }

    /** The student's joined sessions of one card's emails, in time order. */
    public List<SchoolMailJoined> joinedOf(Integer userId, Collection<String> keys) {
        return joined.findByUserIdAndMailKeyInOrderByDayAscStartAsc(userId, keys);
    }

    /** The student's joined sessions of one card's emails that haven't ended at `now` (Vietnam time). */
    public List<SchoolMailJoined> upcomingJoined(Integer userId, Collection<String> keys, LocalDateTime now) {
        return joinedOf(userId, keys).stream().filter(row -> session(row).endAt().isAfter(now)).toList();
    }

    /** The student's added Periods of one card's emails, soonest first. */
    public List<SchoolMailAddedPeriod> addedOf(Integer userId, Collection<String> keys) {
        return added.findByUserIdAndMailKeyInOrderByFirstDayAscLastDayAscFromTimeAsc(userId, keys);
    }

    /** The student's added Periods of one card's emails that haven't ended at `now` (Vietnam time). */
    public List<SchoolMailAddedPeriod> upcomingAdded(Integer userId, Collection<String> keys, LocalDateTime now) {
        return addedOf(userId, keys).stream().filter(row -> period(row).endAt().isAfter(now)).toList();
    }

    /** The emails the student added a Period of. */
    public Set<String> addedKeys(Integer userId) {
        Set<String> keys = new LinkedHashSet<>();
        added.findByUserIdOrderByFirstDayAscLastDayAscFromTimeAsc(userId).forEach(row -> keys.add(row.getMailKey()));
        return keys;
    }

    /**
     * Puts `rows` in place of the student's joined sessions of one card's emails that haven't ended at `now`, and
     * `periods` in place of its added Periods that haven't ended, in one transaction: a Save happens whole or not at
     * all. The old rows go in one statement by id, so rows another Save already removed are no error.
     */
    @Transactional
    public void replaceUpcoming(Integer userId, Collection<String> keys, LocalDateTime now,
            List<SchoolMailJoined> rows, List<SchoolMailAddedPeriod> periods) {
        joined.deleteAllByIdInBatch(upcomingJoined(userId, keys, now).stream().map(SchoolMailJoined::getId).toList());
        added.deleteAllByIdInBatch(upcomingAdded(userId, keys, now).stream().map(SchoolMailAddedPeriod::getId).toList());
        joined.saveAll(rows);
        added.saveAll(periods);
    }

    /** Puts `rows` in place of the joined sessions that haven't ended, and leaves the added Periods as they are. */
    public void replaceUpcoming(Integer userId, Collection<String> keys, LocalDateTime now,
            List<SchoolMailJoined> rows) {
        replaceUpcoming(userId, keys, now, rows, upcomingAdded(userId, keys, now).stream()
                .map(SchoolMailAddedPeriod::copy).toList());
    }

    /**
     * Removes the student's joined sessions and added Periods of one card's emails that haven't ended at `now`, in
     * one transaction.
     */
    @Transactional
    public void leave(Integer userId, Collection<String> keys, LocalDateTime now) {
        joined.deleteAllByIdInBatch(upcomingJoined(userId, keys, now).stream().map(SchoolMailJoined::getId).toList());
        added.deleteAllByIdInBatch(upcomingAdded(userId, keys, now).stream().map(SchoolMailAddedPeriod::getId).toList());
    }

    /** Adds one Period of a card to the Timetable, unless it is there already. */
    @Transactional
    public void add(SchoolMailAddedPeriod row) {
        Period period = period(row);
        if (addedOf(row.getUserId(), List.of(row.getMailKey())).stream().noneMatch(r -> period(r).same(period))) {
            added.save(row);
        }
    }

    /** Removes the student's added copies of this Period of one card's emails; whether there was one. */
    @Transactional
    public boolean remove(Integer userId, Collection<String> keys, String periodId) {
        List<Integer> ids = addedOf(userId, keys).stream().filter(row -> period(row).id().equals(periodId))
                .map(SchoolMailAddedPeriod::getId).toList();
        added.deleteAllByIdInBatch(ids);
        return !ids.isEmpty();
    }

    /**
     * A joined or added event whose email is no longer in the Mailbox: its title, and its joined sessions and added
     * Periods that haven't ended, so the student can still leave it.
     */
    public record Gone(String key, String title, boolean trainingPoints, List<Line> lines, List<PeriodLine> periods) {

        /** The day of the first of them that hasn't ended (today for a running Period). */
        public LocalDate next(LocalDate today) {
            LocalDate first = null;
            for (Line line : lines) {
                first = first == null || line.session().day().isBefore(first) ? line.session().day() : first;
            }
            for (PeriodLine line : periods) {
                LocalDate day = line.period().firstDay().isAfter(today) ? line.period().firstDay() : today;
                first = first == null || day.isBefore(first) ? day : first;
            }
            return first;
        }
    }

    /**
     * The student's joined and added events whose emails are none of `mailKeys` (the Mailbox's) and that have a
     * session or Period that hasn't ended at `now` (Vietnam time), soonest first.
     */
    public List<Gone> gone(Integer userId, Set<String> mailKeys, LocalDateTime now) {
        Map<String, List<SchoolMailJoined>> byKey = new LinkedHashMap<>();
        // From yesterday: a session without an end that starts late in the evening ends after midnight.
        for (SchoolMailJoined row : joined.findByUserIdAndDayGreaterThanEqualOrderByDayAscStartAsc(userId,
                now.toLocalDate().minusDays(1))) {
            if (!mailKeys.contains(row.getMailKey()) && session(row).endAt().isAfter(now)) {
                byKey.computeIfAbsent(row.getMailKey(), key -> new ArrayList<>()).add(row);
            }
        }
        Map<String, List<SchoolMailAddedPeriod>> periodsByKey = new LinkedHashMap<>();
        for (SchoolMailAddedPeriod row : added.findByUserIdAndLastDayGreaterThanEqualOrderByFirstDayAscLastDayAsc(userId,
                now.toLocalDate())) {
            if (!mailKeys.contains(row.getMailKey()) && period(row).endAt().isAfter(now)) {
                periodsByKey.computeIfAbsent(row.getMailKey(), key -> new ArrayList<>()).add(row);
            }
        }
        Set<String> keys = new LinkedHashSet<>(byKey.keySet());
        keys.addAll(periodsByKey.keySet());
        List<Gone> gone = new ArrayList<>();
        for (String key : keys) {
            List<SchoolMailJoined> rows = byKey.getOrDefault(key, List.of());
            List<SchoolMailAddedPeriod> periods = periodsByKey.getOrDefault(key, List.of());
            gone.add(new Gone(key, !rows.isEmpty() ? rows.get(0).getTitle() : periods.get(0).getTitle(),
                    !rows.isEmpty() && rows.get(0).isTrainingPoints(),
                    rows.stream().map(row -> new Line(session(row), false, true, null)).toList(),
                    periods.stream().map(row -> new PeriodLine(period(row), false, true)).toList()));
        }
        LocalDate today = now.toLocalDate();
        gone.sort((a, b) -> a.next(today).compareTo(b.next(today)));
        return gone;
    }

    /**
     * Each event-like or joinable card's sessions (Card.joinable) that haven't ended at `now` (Vietnam time), by card
     * key. A cancelled meeting's are listed too, to be shown struck out.
     */
    @Transactional(readOnly = true)
    public Map<String, List<Line>> lines(Integer userId, List<Card> cards, LocalDateTime now) {
        Map<String, Map<List<Object>, Line>> byCard = new LinkedHashMap<>();
        LocalDate first = null;
        LocalDate last = null;
        for (Card card : cards) {
            if (!card.eventLike() && !card.joinable()) {
                continue;
            }
            Map<List<Object>, Line> lines = new LinkedHashMap<>();
            for (Session s : card.sessions()) {
                lines.put(List.of(s.day(), s.start()), new Line(s, true, false, null));
            }
            for (SchoolMailJoined row : joinedOf(userId, card.keys())) {
                Session s = session(row);
                if (s.endAt().isAfter(now)) {
                    Line found = lines.get(List.of(s.day(), s.start()));
                    lines.put(List.of(s.day(), s.start()),
                            new Line(found != null ? found.session() : s, found != null, true, null));
                }
            }
            byCard.put(card.key(), lines);
            for (List<Object> key : lines.keySet()) {
                LocalDate day = (LocalDate) key.get(0);
                first = first == null || day.isBefore(first) ? day : first;
                last = last == null || day.isAfter(last) ? day : last;
            }
        }
        Map<String, List<Line>> result = new LinkedHashMap<>();
        if (first == null) {
            return result;
        }
        // A day more on each side: a session can start at its check-in the day before, or end the day after.
        List<Busy> timetable = timetable(userId, first.minusDays(1), last.plusDays(1));
        List<SchoolMailJoined> allJoined = joined.findByUserIdAndDayBetweenOrderByDayAscStartAsc(userId,
                first.minusDays(1), last.plusDays(1));
        for (Card card : cards) {
            Map<List<Object>, Line> lines = byCard.get(card.key());
            if (lines == null || lines.isEmpty()) {
                continue;
            }
            List<Busy> busy = new ArrayList<>(timetable);
            for (SchoolMailJoined row : allJoined) {
                if (!card.keys().contains(row.getMailKey())) {
                    Session s = session(row);
                    busy.add(new Busy(row.getTitle(), s.busyFrom(), s.endAt()));
                }
            }
            result.put(card.key(), lines.values().stream()
                    .sorted((a, b) -> Session.ORDER.compare(a.session(), b.session()))
                    .map(l -> new Line(l.session(), l.found(), l.joined(), Conflicts.of(l.session(), busy)))
                    .toList());
        }
        return result;
    }

    /** One card's lines, as {@link #lines(Integer, List, LocalDateTime)} gives them. */
    public List<Line> lines(Integer userId, Card card, LocalDateTime now) {
        return lines(userId, List.of(card), now).getOrDefault(card.key(), List.of());
    }

    /**
     * Each event-like or joinable card's Periods that haven't ended at `now` (Vietnam time): the ones found in its
     * emails and the ones the student added (also those its emails no longer give), soonest first, by card key.
     */
    @Transactional(readOnly = true)
    public Map<String, List<PeriodLine>> periodLines(Integer userId, List<Card> cards, LocalDateTime now) {
        Map<String, List<PeriodLine>> result = new LinkedHashMap<>();
        for (Card card : cards) {
            if (!card.eventLike() && !card.joinable()) {
                continue;
            }
            Map<String, PeriodLine> lines = new LinkedHashMap<>();
            for (Period p : card.periods()) {
                lines.put(p.id(), new PeriodLine(p, true, false));
            }
            if (card.added()) {
                for (SchoolMailAddedPeriod row : upcomingAdded(userId, card.keys(), now)) {
                    Period p = period(row);
                    PeriodLine found = lines.get(p.id());
                    lines.put(p.id(), new PeriodLine(found != null ? found.period() : p, found != null, true));
                }
            }
            if (!lines.isEmpty()) {
                result.put(card.key(), lines.values().stream()
                        .sorted((a, b) -> Period.ORDER.compare(a.period(), b.period())).toList());
            }
        }
        return result;
    }

    /** One card's Period lines, as {@link #periodLines(Integer, List, LocalDateTime)} gives them. */
    public List<PeriodLine> periodLines(Integer userId, Card card, LocalDateTime now) {
        return periodLines(userId, List.of(card), now).getOrDefault(card.key(), List.of());
    }

    /**
     * Classes and exams on the Vietnam days [first, last], as the Timetable shows them: cancelled classes, classes
     * without a time and joined events (counted apart, without the card's own) are left out.
     */
    private List<Busy> timetable(Integer userId, LocalDate first, LocalDate last) {
        List<Busy> busy = new ArrayList<>();
        List<Item> items = schedule.itemsBetween(userId, VietnamTime.dayStart(first),
                VietnamTime.dayStart(last.plusDays(1)));
        for (Item item : items) {
            if (item.allDay() || "cancelled".equals(item.change()) || "event".equals(item.kind())) {
                continue;
            }
            LocalDateTime start = VietnamTime.of(item.startAt()).toLocalDateTime();
            LocalDateTime end = item.endAt() != null ? VietnamTime.of(item.endAt()).toLocalDateTime()
                    : start.plus(EXAM_WITHOUT_LENGTH);
            busy.add(new Busy(item.label() != null ? item.label() + ": " + item.title() : item.title(), start, end));
        }
        return busy;
    }
}
