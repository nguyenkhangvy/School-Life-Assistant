package vn.edu.hcmiu.sla.school.mail;

import java.text.Normalizer;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import vn.edu.hcmiu.sla.school.VietnamTime;
import vn.edu.hcmiu.sla.school.model.SchoolMail;
import vn.edu.hcmiu.sla.school.model.SchoolMailChoice;

/**
 * What the Mailbox tab shows: emails grouped into cards, cards in boxes, in the order of
 * docs/superpowers/specs/2026-09-28-outlook-mailbox-design.md, section 6.3, with the sessions, Past and opening
 * rules of 2026-09-28-mailbox-events-design.md, section 4, and the Periods, deadlines, tags and flags of
 * 2026-10-07-mail-event-kinds-design.md, section 6.2. Pure functions; times are Vietnam wall-clock times.
 */
public final class Mailbox {

    private Mailbox() {
    }

    /** The categories in the order they are shown, with their names. */
    public static final Map<String, String> CATEGORIES = orderedNames(
            "class", "Class", "school_task", "School task", "money", "Money", "event", "Event",
            "training_points", "Training points", "requests_account", "Your requests & account",
            "system_notice", "System notice", "promotion", "Promotion");
    /** The short names on a card's labels. */
    public static final Map<String, String> LABELS = orderedNames(
            "class", "Class", "school_task", "Task", "money", "Money", "event", "Event",
            "training_points", "★ Points", "requests_account", "Requests", "system_notice", "System",
            "promotion", "Promo");
    static final Duration SAME_EMAIL_WINDOW = Duration.ofDays(30);
    /** How long a session without an end lasts. */
    public static final Duration SESSION_WITHOUT_END = Duration.ofHours(1);

    private static Map<String, String> orderedNames(String... pairs) {
        Map<String, String> names = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) {
            names.put(pairs[i], pairs[i + 1]);
        }
        return Collections.unmodifiableMap(names);
    }

    /**
     * One time an event takes place, as the laptop found it. Vietnam time; end may be empty, and is on the next day
     * when endsNextDay. checkIn: when to be there by, from which the session is busy; linkOpens: when an online
     * event's link opens. mode (online, in_person), relative (the word its day came from) and label are codes from the
     * upload format's lists.
     */
    public record Session(LocalDate day, LocalTime start, LocalTime end, boolean endIsApproximate, boolean endsNextDay,
            LocalTime checkIn, LocalTime linkOpens, String mode, String relative, String label) {

        static final Comparator<Session> ORDER = Comparator.comparing(Session::day).thenComparing(Session::start);

        /** A day, a start and maybe an end, and nothing else known. */
        public Session(LocalDate day, LocalTime start, LocalTime end) {
            this(day, start, end, false, false, null, null, null, null, null);
        }

        public LocalDateTime startAt() {
            return day.atTime(start);
        }

        /** When the student must be there: the check-in, or else the start. The session is busy from then. */
        public LocalDateTime busyFrom() {
            return checkIn != null && checkIn.isBefore(start) ? day.atTime(checkIn) : startAt();
        }

        /** The end (on the next day when it ends then), or an hour after the start when the email gave none. */
        public LocalDateTime endAt() {
            if (end == null) {
                return startAt().plus(SESSION_WITHOUT_END);
            }
            return (endsNextDay ? day.plusDays(1) : day).atTime(end);
        }
    }

    /**
     * A range of days in which the student may come or do something at any time: mode all_day (no times),
     * daily_window (fromTime–toTime each day) or one_window (from fromTime on the first day to toTime on the last).
     * detailsLater: the student's own time comes later. Never busy.
     */
    public record Period(LocalDate firstDay, LocalDate lastDay, String mode, LocalTime fromTime, LocalTime toTime,
            boolean detailsLater, String label) {

        static final Comparator<Period> ORDER = Comparator.comparing(Period::firstDay).thenComparing(Period::lastDay)
                .thenComparing(Period::fromTime, Comparator.nullsFirst(Comparator.naturalOrder()));

        public boolean allDay() {
            return "all_day".equals(mode);
        }

        /** When it ends: at toTime on its last day, or at the end of that day when it has no times. */
        public LocalDateTime endAt() {
            return toTime != null ? lastDay.atTime(toTime) : lastDay.plusDays(1).atStartOfDay();
        }

        /** How forms name it: "2026-11-02/2026-11-05/daily_window/09:00", or "…/all_day/-" without a time. */
        public String id() {
            return firstDay + "/" + lastDay + "/" + mode + "/" + (fromTime != null ? MailTexts.clock(fromTime) : "-");
        }

        /** The same Period (its days, mode and start): an added copy of a found one. */
        boolean same(Period other) {
            return id().equals(other.id());
        }
    }

    /**
     * A deadline the laptop found: kind opens (registration opens), register (it closes), confirm or due, with its
     * day, maybe a time and a mode (online, in_person). Information only, never event time.
     */
    public record Deadline(String kind, LocalDate day, LocalTime time, String mode) {

        static final Comparator<Deadline> ORDER = Comparator.comparing(Deadline::at).thenComparing(Deadline::kind)
                .thenComparing(Deadline::mode, Comparator.nullsFirst(Comparator.naturalOrder()));

        /** When it takes effect: at its time; else an opening at the start of its day, any other at the end. */
        public LocalDateTime at() {
            if (time != null) {
                return day.atTime(time);
            }
            return "opens".equals(kind) ? day.atStartOfDay() : day.plusDays(1).atStartOfDay();
        }

        public boolean passed(LocalDateTime now) {
            return !now.isBefore(at());
        }

        /** "Register by 12:00 Sat 10/10 · In person" (MailTexts). */
        public String text() {
            return MailTexts.deadline(this);
        }
    }

    /** What the laptop found in the emails, by mail key. */
    public record Found(Map<String, List<Session>> sessions, Map<String, List<Period>> periods,
            Map<String, List<Deadline>> deadlines) {

        public Found {
            sessions = sessions == null ? Map.of() : sessions;
            periods = periods == null ? Map.of() : periods;
            deadlines = deadlines == null ? Map.of() : deadlines;
        }
    }

    /** What the student did: the emails they joined a session of, and those they added a Period of. */
    public record Mine(Set<String> joinedKeys, Set<String> addedKeys) {

        public static final Mine NOTHING = new Mine(Set.of(), Set.of());
    }

    /** A part of a tag; passed: its time has passed, so it is struck out. */
    public record Piece(String text, boolean passed) {
    }

    /**
     * A tag on a card's row: kind (register, closed, confirm or due, for its look), its lead ("Register by 17:00 Mon
     * 12/10", or "Register by:") and, when a deadline has a mode, one piece per mode.
     */
    public record Tag(String kind, String lead, List<Piece> pieces) {

        static Tag of(String kind, String text) {
            return new Tag(kind, text, List.of());
        }

        /** The whole tag as text: "Register by: In person 12:00 Sat 03/10 · Online 17:00 Mon 12/10". */
        public String text() {
            return pieces.isEmpty() ? lead
                    : lead + " " + pieces.stream().map(Piece::text).collect(Collectors.joining(" · "));
        }
    }

    /**
     * One card: a thread, or the same email sent more than once. key, entryId, sender, subject and time come
     * from its newest email; keys are all its emails' keys. eventLike: an event or school task, or a lecturer's
     * meeting or class activity with a time (Class with the meeting flag and a session); only those show sessions and
     * Periods, have Join… and stay in their box when opened while ahead. sessions and periods: an event-like card's
     * that haven't ended (none for other cards). nextDate: the day of the first of them (today for a running Period),
     * or else the earliest date from today on. over: every session and Period has ended, or (without them) every date
     * is over. past: it is over, or (an event) its registration closed and the student joined and added nothing and
     * isn't registered. suggested: the student moved it to Event or School task and the rules gave it neither, so its
     * sessions are only suggestions. deadlines: its emails' deadlines, soonest first; registerBy: the latest register
     * day of them, or null; closed: its registration has closed. tags: what its deadlines say on its row. joined and
     * added: the student joined a session, or added a Period, of one of its emails. registered: an email confirms the
     * student is registered. cancelled: its newest email cancels an Outlook meeting.
     */
    public record Card(String key, List<String> keys, String entryId, String senderName, String subject,
            LocalDateTime receivedAt, List<String> categories, boolean fromLecturer, boolean moved,
            List<LocalDate> dates, boolean eventLike, List<Session> sessions, List<Period> periods,
            LocalDate nextDate, boolean over, boolean past, boolean sorted, boolean opened, boolean done, int messages,
            int copies, boolean suggested, List<Deadline> deadlines, LocalDate registerBy, boolean closed,
            List<Tag> tags, boolean joined, boolean added, boolean registered, boolean cancelled) {

        public boolean trainingPoints() {
            return categories.contains("training_points");
        }

        /**
         * Join… and Leave are open to it: an event-like card (unless its meeting was cancelled), or a card the
         * student joined or added something of, even after moving it away.
         */
        public boolean joinable() {
            return (eventLike && !cancelled) || joined || added;
        }

        /** Its row offers Add: it has exactly one Period and no sessions, and wasn't cancelled. */
        public boolean addable() {
            return !cancelled && sessions.isEmpty() && periods.size() == 1;
        }

        /**
         * With auto-Done on, opening it marks it Done: anything but an event or school task still ahead, or one in
         * Past only because its registration closed (Past and Done stay apart).
         */
        public boolean doneWhenOpened() {
            return !(eventLike && (nextDate != null || (past && !over)));
        }

        LocalDate lastDate() {
            return dates.isEmpty() ? null : dates.get(dates.size() - 1);
        }
    }

    /** A box. cards: shown, all of them; past: in its closed "Past" list (Events and School tasks only). */
    public record Box(String id, String title, List<Card> cards, List<Card> past, String pastTitle) {

        public boolean empty() {
            return cards.isEmpty() && past.isEmpty();
        }
    }

    /** The boxes in order, and the closed "Done" list. */
    public record View(List<Box> boxes, List<Card> done) {

        public Card card(String key) {
            return boxes.stream().flatMap(b -> Stream.of(b.cards(), b.past()))
                    .flatMap(List::stream).filter(c -> c.key().equals(key))
                    .findFirst()
                    .orElseGet(() -> done.stream().filter(c -> c.key().equals(key)).findFirst().orElse(null));
        }

        /** Every email's key, of every card. */
        public Set<String> keys() {
            return Stream.concat(boxes.stream().flatMap(b -> Stream.of(b.cards(), b.past())), Stream.of(done))
                    .flatMap(List::stream).flatMap(c -> c.keys().stream()).collect(Collectors.toSet());
        }
    }

    static boolean eventLike(List<String> categories) {
        return categories.contains("event") || categories.contains("school_task");
    }

    /** Lower case, letters and digits only, one space between words: how "the same subject" is compared. */
    static String sameSubject(String subject) {
        String text = Normalizer.normalize(subject, Normalizer.Form.NFC).toLowerCase(Locale.ROOT);
        return text.replaceAll("[^\\p{L}\\p{N}]+", " ").strip();
    }

    /** A card's emails, newest first, and how many separate sends it merged. */
    private record Group(List<SchoolMail> mails, int copies) {
    }

    /** Emails of one thread form a group; groups with the same sender and subject within 30 days merge. */
    private static List<Group> groups(List<SchoolMail> newestFirst) {
        Map<String, List<SchoolMail>> threads = new LinkedHashMap<>();
        for (SchoolMail mail : newestFirst) {
            String thread = mail.getThreadId() != null ? "t:" + mail.getThreadId() : "k:" + mail.getMailKey();
            threads.computeIfAbsent(thread, t -> new ArrayList<>()).add(mail);
        }
        List<List<SchoolMail>> merged = new ArrayList<>();
        List<Integer> copies = new ArrayList<>();
        // The groups so far by sender and subject, so a thread is only compared with those it could be a copy of.
        Map<String, List<Integer>> alike = new HashMap<>();
        for (List<SchoolMail> thread : threads.values()) {
            SchoolMail mail = thread.get(0);
            List<Integer> candidates = alike.computeIfAbsent(
                    mail.getSenderAddress().toLowerCase(Locale.ROOT) + "\n" + sameSubject(mail.getSubject()),
                    k -> new ArrayList<>());
            Integer same = candidates.stream().filter(i -> Duration.between(mail.getReceivedAt(),
                    merged.get(i).get(0).getReceivedAt()).abs().compareTo(SAME_EMAIL_WINDOW) <= 0)
                    .findFirst().orElse(null);
            if (same != null) {
                merged.get(same).addAll(thread);
                copies.set(same, copies.get(same) + 1);
            } else {
                candidates.add(merged.size());
                merged.add(new ArrayList<>(thread));
                copies.add(1);
            }
        }
        List<Group> groups = new ArrayList<>();
        for (int i = 0; i < merged.size(); i++) {
            List<SchoolMail> mails = merged.get(i);
            mails.sort(Comparator.comparing(SchoolMail::getReceivedAt).reversed());
            groups.add(new Group(mails, copies.get(i)));
        }
        return groups;
    }

    /** A card's emails' sessions, each day and start once (one with an end wins), in time order. */
    private static List<Session> sessionsOf(List<SchoolMail> mails, Map<String, List<Session>> sessions) {
        Map<List<Object>, Session> kept = new LinkedHashMap<>();
        for (SchoolMail mail : mails) {
            for (Session s : sessions.getOrDefault(mail.getMailKey(), List.of())) {
                kept.merge(List.of(s.day(), s.start()), s, (old, now) -> old.end() != null ? old : now);
            }
        }
        return kept.values().stream().sorted(Session.ORDER).toList();
    }

    /** A card's emails' Periods, each once (the newest email's wins), soonest first. */
    private static List<Period> periodsOf(List<SchoolMail> mails, Map<String, List<Period>> periods) {
        Map<String, Period> kept = new LinkedHashMap<>();
        for (SchoolMail mail : mails) {
            for (Period p : periods.getOrDefault(mail.getMailKey(), List.of())) {
                kept.putIfAbsent(p.id(), p);
            }
        }
        return kept.values().stream().sorted(Period.ORDER).toList();
    }

    /**
     * A card's emails' deadlines, each once, soonest first. An email an older agent read has only its registration
     * deadline's day (A.2), which counts as a register deadline.
     */
    private static List<Deadline> deadlinesOf(List<SchoolMail> mails, Map<String, List<Deadline>> deadlines) {
        Set<Deadline> kept = new LinkedHashSet<>();
        for (SchoolMail mail : mails) {
            List<Deadline> found = deadlines.getOrDefault(mail.getMailKey(), List.of());
            if (found.isEmpty() && mail.getRegisterBy() != null) {
                found = List.of(new Deadline("register", mail.getRegisterBy(), null, null));
            }
            kept.addAll(found);
        }
        return kept.stream().sorted(Deadline.ORDER).toList();
    }

    /** For each mode, the deadline of this kind that `pick` prefers among the card's. */
    private static List<Deadline> eachMode(List<Deadline> deadlines, String kind, Comparator<Deadline> pick) {
        Map<String, Deadline> kept = new LinkedHashMap<>();
        for (Deadline d : deadlines) {
            if (d.kind().equals(kind)) {
                kept.merge(String.valueOf(d.mode()), d, (a, b) -> pick.compare(b, a) > 0 ? b : a);
            }
        }
        return kept.values().stream().sorted(Deadline.ORDER).toList();
    }

    private static final Comparator<Deadline> LATEST = Comparator.comparing(Deadline::at);

    /** A card's registration: before its earliest opening, open, or closed after its last register deadline. */
    enum Registration { NONE, NOT_OPEN, OPEN, CLOSED }

    /**
     * Its registration from its opens and register deadlines (spec 6.2). For each kind and mode the latest counts, so
     * a reminder can extend it (A.3).
     */
    static Registration registration(List<Deadline> deadlines, LocalDateTime now) {
        List<Deadline> opens = eachMode(deadlines, "opens", LATEST);
        List<Deadline> register = eachMode(deadlines, "register", LATEST);
        if (opens.isEmpty() && register.isEmpty()) {
            return Registration.NONE;
        }
        if (!register.isEmpty() && register.get(register.size() - 1).passed(now)) {
            return Registration.CLOSED;
        }
        if (!opens.isEmpty() && !opens.get(0).passed(now)) {
            return Registration.NOT_OPEN;
        }
        return Registration.OPEN;
    }

    /** One tag for these deadlines of one kind: "Register by 17:00 Mon 12/10", or by mode, a passed one struck out. */
    private static Tag deadlineTag(String kind, String lead, List<Deadline> deadlines, LocalDateTime now) {
        if (deadlines.stream().allMatch(d -> d.mode() == null) && deadlines.size() == 1) {
            return Tag.of(kind, lead + " " + MailTexts.when(deadlines.get(0)));
        }
        return new Tag(kind, lead + ":", deadlines.stream().map(d -> new Piece(
                (d.mode() != null ? MailTexts.mode(d.mode()) + " " : "") + MailTexts.when(d), d.passed(now))).toList());
    }

    /**
     * The tags of a card's deadlines (spec 6.2): its registration unless registered ("Registration opens Thu 08/10,
     * closes Mon 12/10", "Register by …" while open and not Past, "Registration closed" in Past), then "Confirm by …"
     * and "Due …" while their time hasn't passed, the soonest of each mode.
     */
    static List<Tag> tags(List<Deadline> deadlines, Registration registration, boolean registered, boolean past,
            LocalDateTime now) {
        List<Tag> tags = new ArrayList<>();
        if (!registered) {
            List<Deadline> register = eachMode(deadlines, "register", LATEST);
            if (registration == Registration.NOT_OPEN && !past) {
                Deadline opens = eachMode(deadlines, "opens", LATEST).get(0);
                tags.add(Tag.of("register", "Registration opens " + VietnamTime.dayLabel(opens.day())
                        + (register.isEmpty() ? "" : ", closes "
                                + VietnamTime.dayLabel(register.get(register.size() - 1).day()))));
            } else if (registration == Registration.OPEN && !past) {
                tags.add(register.isEmpty() ? Tag.of("register", "Registration open")
                        : deadlineTag("register", "Register by", register, now));
            } else if (registration == Registration.CLOSED && past) {
                tags.add(Tag.of("closed", "Registration closed"));
            }
        }
        for (String[] kind : new String[][] {{"confirm", "Confirm by"}, {"due", "Due"}}) {
            List<Deadline> ahead = eachMode(deadlines.stream().filter(d -> !d.passed(now)).toList(), kind[0],
                    LATEST.reversed());
            if (!ahead.isEmpty()) {
                tags.add(deadlineTag(kind[0], kind[1], ahead, now));
            }
        }
        return tags;
    }

    private static Card card(Group group, Map<String, SchoolMailChoice> choices, Found found, Mine mine,
            LocalDateTime now) {
        List<SchoolMail> mails = group.mails();
        SchoolMail newest = mails.get(0);
        SchoolMailChoice moved = mails.stream().map(m -> choices.get(m.getMailKey()))
                .filter(c -> c != null && c.isMoved()).findFirst().orElse(null);
        SchoolMailChoice newestChoice = choices.get(newest.getMailKey());
        List<String> categories = moved != null && moved.getCategories() != null ? moved.getCategories()
                : newest.getCategories();
        boolean fromLecturer = moved != null && moved.getFromLecturer() != null ? moved.getFromLecturer()
                : newest.isFromLecturer();
        TreeSet<LocalDate> dates = new TreeSet<>();
        mails.forEach(m -> dates.addAll(m.getDates()));
        List<Session> all = sessionsOf(mails, found.sessions());
        boolean meeting = mails.stream().anyMatch(SchoolMail::isMeeting);
        boolean eventLike = eventLike(categories) || (categories.contains("class") && meeting && !all.isEmpty());
        if (!eventLike) {
            all = List.of();
        }
        List<Period> periods = eventLike ? periodsOf(mails, found.periods()) : List.of();
        List<Session> ahead = all.stream().filter(s -> s.endAt().isAfter(now)).toList();
        List<Period> periodsAhead = periods.stream().filter(p -> p.endAt().isAfter(now)).toList();
        LocalDate today = now.toLocalDate();
        boolean timed = !all.isEmpty() || !periods.isEmpty();
        LocalDate next = !timed ? dates.ceiling(today) : Stream.concat(ahead.stream().map(Session::day),
                periodsAhead.stream().map(p -> p.firstDay().isAfter(today) ? p.firstDay() : today))
                .min(Comparator.naturalOrder()).orElse(null);
        List<Deadline> deadlines = deadlinesOf(mails, found.deadlines());
        LocalDate registerBy = deadlines.stream().filter(d -> d.kind().equals("register")).map(Deadline::day)
                .max(Comparator.naturalOrder()).orElse(null);
        Registration registration = registration(deadlines, now);
        boolean closed = registration == Registration.CLOSED;
        boolean joined = mails.stream().anyMatch(m -> mine.joinedKeys().contains(m.getMailKey()));
        boolean added = mails.stream().anyMatch(m -> mine.addedKeys().contains(m.getMailKey()));
        boolean registered = mails.stream().anyMatch(SchoolMail::isRegistered);
        boolean over = !timed ? !dates.isEmpty() && next == null : ahead.isEmpty() && periodsAhead.isEmpty();
        boolean past = over || (categories.contains("event") && closed && !joined && !added && !registered);
        return new Card(newest.getMailKey(), mails.stream().map(SchoolMail::getMailKey).toList(), newest.getEntryId(),
                newest.getSenderName(), newest.getSubject(), newest.getReceivedAt(), categories, fromLecturer,
                moved != null, List.copyOf(dates), eventLike, ahead, periodsAhead, next, over, past, newest.isSorted(),
                newestChoice != null && newestChoice.isOpened(), newestChoice != null && newestChoice.isDone(),
                mails.size(), group.copies(), eventLike(categories) && !eventLike(newest.getCategories()), deadlines,
                registerBy, closed, tags(deadlines, registration, registered, past, now), joined, added, registered,
                "cancelled".equals(newest.getInvitation()));
    }

    private static final Comparator<Card> NEWEST_FIRST = Comparator.comparing(Card::receivedAt).reversed();
    private static final Comparator<Card> SOONEST_FIRST = Comparator.comparing(Card::nextDate,
            Comparator.nullsLast(Comparator.naturalOrder())).thenComparing(NEWEST_FIRST);
    private static final Comparator<Card> LATEST_DATE_FIRST = Comparator.comparing(Card::lastDate,
            Comparator.nullsLast(Comparator.<LocalDate>reverseOrder())).thenComparing(NEWEST_FIRST);

    private static String boxOf(Card card) {
        if (card.fromLecturer()) {
            return "lecturers";
        }
        for (String[] box : new String[][] {{"school_task", "tasks"}, {"money", "money"}, {"event", "events"}}) {
            if (card.categories().contains(box[0])) {
                return box[1];
            }
        }
        return "other";
    }

    /** The whole tab, for a student who joined no events, from emails with sessions only. */
    public static View build(List<SchoolMail> mails, Map<String, SchoolMailChoice> choices,
            Map<String, List<Session>> sessions, LocalDateTime now) {
        return build(mails, choices, sessions, Set.of(), now);
    }

    /** The whole tab, from emails with sessions only; joinedKeys: the emails with a joined session. */
    public static View build(List<SchoolMail> mails, Map<String, SchoolMailChoice> choices,
            Map<String, List<Session>> sessions, Set<String> joinedKeys, LocalDateTime now) {
        return build(mails, choices, new Found(sessions, Map.of(), Map.of()), new Mine(joinedKeys, Set.of()), now);
    }

    /**
     * The whole tab. mails: newest first; choices by mail key; found: what the laptop found, by mail key; mine: the
     * emails the student joined or added something of; now in Vietnam (wall clock).
     */
    public static View build(List<SchoolMail> mails, Map<String, SchoolMailChoice> choices, Found found, Mine mine,
            LocalDateTime now) {
        Map<String, List<Card>> byBox = new LinkedHashMap<>();
        for (String box : List.of("lecturers", "tasks", "money", "events", "other")) {
            byBox.put(box, new ArrayList<>());
        }
        List<Card> done = new ArrayList<>();
        for (Group group : groups(mails)) {
            Card card = card(group, choices, found, mine, now);
            (card.done() ? done : byBox.get(boxOf(card))).add(card);
        }
        done.sort(NEWEST_FIRST);

        List<Card> events = byBox.get("events");
        List<Card> tasks = byBox.get("tasks");
        List<Card> other = byBox.get("other");
        byBox.get("lecturers").sort(NEWEST_FIRST);
        byBox.get("money").sort(NEWEST_FIRST);
        other.sort(NEWEST_FIRST);
        List<Box> boxes = List.of(
                new Box("lecturers", "From lecturers", byBox.get("lecturers"), List.of(), null),
                new Box("tasks", "School tasks", current(tasks, SOONEST_FIRST), past(tasks), "Past"),
                new Box("money", "Money", byBox.get("money"), List.of(), null),
                new Box("events", "Events", current(events, Comparator.comparing((Card c) -> !c.trainingPoints())
                        .thenComparing(SOONEST_FIRST)), past(events), "Past events"),
                new Box("other", "Everything else", other, List.of(), null));
        return new View(boxes, done);
    }

    private static List<Card> current(List<Card> cards, Comparator<Card> order) {
        return cards.stream().filter(c -> !c.past()).sorted(order).toList();
    }

    private static List<Card> past(List<Card> cards) {
        return cards.stream().filter(Card::past).sorted(LATEST_DATE_FIRST).toList();
    }

    /** Whether these are allowed Move to… categories: one or two known ones, different. */
    public static boolean validCategories(List<String> categories) {
        return !categories.isEmpty() && categories.size() <= 2
                && categories.stream().allMatch(c -> c != null && CATEGORIES.containsKey(c))
                && categories.stream().distinct().count() == categories.size();
    }
}
