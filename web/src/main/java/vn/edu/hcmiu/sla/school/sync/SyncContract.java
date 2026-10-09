package vn.edu.hcmiu.sla.school.sync;

import java.time.LocalDate;
import java.time.LocalTime;
import java.time.OffsetDateTime;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

/**
 * The data the laptop agent sends to the website after a sync: the Java twin of
 * contract/sla_contract/schema.py, which the agent uses. Change both together.
 *
 * <p>{@link SyncJson} reads it: field names are snake_case in JSON (course_code), unknown fields are
 * refused so nothing extra can leave the laptop, text is trimmed, and times must carry their offset.
 * Text limits use {@link Chars} (characters, as pydantic counts them); list limits use {@code @Size}.
 */
public final class SyncContract {

    private SyncContract() {
    }

    static final String ERROR_CODES = "bad_credentials|session_expired|network|edusoft_changed|source_changed"
            + "|extra_verification|outlook_not_set_up|outlook_blocked|unknown";
    public static final String MAIL_CATEGORIES =
            "class|event|training_points|school_task|money|requests_account|system_notice|promotion";
    static final String BLACKBOARD_URL = "(?s)https://blackboard\\.hcmiu\\.edu\\.vn/.*";

    public record StartRun(@NotNull @Pattern(regexp = "scheduled|manual|import|mail") String trigger) {
    }

    // ---- Connect this laptop (spec 2026-10-04-connect-button-design.md, 3) --------------

    /** A Connect code, state, verifier or challenge: 32 random bytes, URL-safe Base64 without padding. */
    public static final String CONNECT_SECRET = "[A-Za-z0-9_-]{43}";

    /** The trade-in: the one-time code the browser brought back, and the verifier only the app knows. */
    public record ConnectRequest(@NotNull @Pattern(regexp = CONNECT_SECRET) String code,
            @NotNull @Pattern(regexp = CONNECT_SECRET) String verifier) {
    }

    // ---- EduSoft ----------------------------------------------------------------

    public record ClassMeeting(@NotNull OffsetDateTime startAt, @NotNull OffsetDateTime endAt,
            @Chars(max = 50) String room) {

        @AssertTrue(message = "end_at must be after start_at")
        boolean isEndAfterStart() {
            return startAt == null || endAt == null || endAt.isAfter(startAt);
        }
    }

    public record Course(
            @NotNull @Chars(min = 1, max = 20) String courseCode,
            @NotNull @Chars(min = 1, max = 255) String courseName,
            @Chars(max = 20) String group,
            @PositiveOrZero @DecimalMax("50") Double credits,
            @Chars(max = 255) String lecturer,
            @Size(max = 200) List<@Valid ClassMeeting> meetings) {

        public Course {
            meetings = meetings == null ? List.of() : meetings;
        }
    }

    public record Timetable(
            @NotNull @Chars(min = 1, max = 20) String termCode,
            @Chars(max = 100) String termName,
            @NotNull @Size(max = 40) List<@Valid Course> courses) {
    }

    public record Exam(
            @NotNull @Chars(min = 1, max = 20) String courseCode,
            @NotNull @Chars(min = 1, max = 255) String courseName,
            @NotNull @Pattern(regexp = "midterm|final|other") String examType,
            @NotNull OffsetDateTime startAt,
            @Min(1) @Max(600) Integer durationMin,
            @Chars(max = 50) String room,
            @Chars(max = 500) String notes) {
    }

    public record Exams(
            @NotNull @Chars(min = 1, max = 20) String termCode,
            @NotNull @Size(max = 60) List<@Valid Exam> exams) {
    }

    /** Amounts are VND. */
    public record TuitionItem(@NotNull @Chars(min = 1, max = 255) String description, @NotNull Long amount) {
    }

    /** Amounts are VND; a negative balance means overpaid. */
    public record Tuition(
            @NotNull @Chars(min = 1, max = 20) String termCode,
            @NotNull @PositiveOrZero Long amountDue,
            @NotNull @PositiveOrZero Long amountPaid,
            @NotNull Long balance,
            LocalDate dueDate,
            @Chars(max = 255) String statusText,
            @Size(max = 60) List<@Valid TuitionItem> items) {

        public Tuition {
            items = items == null ? List.of() : items;
        }
    }

    // ---- IUPay ------------------------------------------------------------------

    static final String BILL_STATUSES = "unpaid|paid|paying|partly_paid";

    /** One IUPay bill. Amounts are VND; dueDate and paidOn are Vietnam dates. */
    public record TuitionBill(
            @NotNull @Chars(min = 1, max = 40) String billNo,
            @NotNull @Chars(min = 1, max = 20) String termCode,
            @Chars(min = 1, max = 255) String termName,
            @NotNull @Chars(min = 1, max = 1000) String description,
            @Chars(min = 1, max = 255) String feeType,
            @NotNull @PositiveOrZero Long amount,
            @PositiveOrZero Long discount,
            @PositiveOrZero Long fee,
            @NotNull @Pattern(regexp = BILL_STATUSES) String status,
            LocalDate dueDate,
            LocalDate paidOn,
            @Chars(max = 100) String channel) {

        public TuitionBill {
            discount = discount == null ? 0L : discount;
            fee = fee == null ? 0L : fee;
        }
    }

    /** Every bill IUPay lists for the student, paid or not. */
    public record Iupay(@Size(max = 500) List<@Valid TuitionBill> bills) {

        public Iupay {
            bills = bills == null ? List.of() : bills;
        }

        @AssertTrue(message = "bill_no must differ")
        boolean isEachBillOnce() {
            return bills.stream().map(TuitionBill::billNo).distinct().count() == bills.size();
        }
    }

    // ---- Blackboard -------------------------------------------------------------

    public record BbAnnouncement(
            @NotNull @Chars(min = 1, max = 64) String bbId,
            @NotNull @Chars(min = 1, max = 255) String title,
            @Chars(max = 5000) String text,
            OffsetDateTime postedAt,
            @NotNull @Chars(max = 500) @Pattern(regexp = BLACKBOARD_URL) String url) {

        public BbAnnouncement {
            text = text == null ? "" : text;
        }
    }

    public record BbAssignment(
            @NotNull @Chars(min = 1, max = 64) String bbId,
            @NotNull @Chars(min = 1, max = 255) String name,
            OffsetDateTime dueAt,
            @PositiveOrZero Double pointsPossible,
            Double score,
            @Chars(max = 50) String gradeText,
            @NotNull @Pattern(regexp = "not_graded|needs_grading|graded|exempt") String status,
            @Chars(max = 1000) String feedback,
            @NotNull @Chars(max = 500) @Pattern(regexp = BLACKBOARD_URL) String url) {
    }

    public record BbMaterial(
            @NotNull @Chars(min = 1, max = 64) String bbId,
            @NotNull @Chars(min = 1, max = 255) String title,
            @NotNull @Pattern(regexp = "file|folder|link|document|other") String kind,
            @Chars(max = 500) String path,
            OffsetDateTime createdAt,
            @NotNull @Chars(max = 500) @Pattern(regexp = BLACKBOARD_URL) String url) {

        public BbMaterial {
            path = path == null ? "" : path;
        }
    }

    public record BbCourse(
            @NotNull @Chars(min = 1, max = 64) String bbId,
            @Chars(min = 1, max = 20) String courseCode,
            @NotNull @Chars(min = 1, max = 255) String name,
            @NotNull @Chars(max = 500) @Pattern(regexp = BLACKBOARD_URL) String url,
            @Size(max = 300) List<@Valid BbAnnouncement> announcements,
            @Size(max = 300) List<@Valid BbAssignment> assignments,
            @Size(max = 1000) List<@Valid BbMaterial> materials) {

        public BbCourse {
            announcements = announcements == null ? List.of() : announcements;
            assignments = assignments == null ? List.of() : assignments;
            materials = materials == null ? List.of() : materials;
        }
    }

    public record Blackboard(@NotNull @Size(max = 40) List<@Valid BbCourse> courses) {
    }

    // ---- Outlook ------------------------------------------------------------------

    /** A class change a lecturer's email announces. day and times are Vietnam time. */
    public record MailClassChange(
            @NotNull @Chars(min = 1, max = 20) String courseCode,
            @NotNull @Pattern(regexp = "online|cancelled|makeup") String kind,
            @NotNull LocalDate day,
            LocalTime start,
            LocalTime end,
            @Chars(max = 50) String room) {
    }

    // Codes from fixed lists, never the email's words (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md,
    // 3.2).
    public static final String MAIL_LABELS =
            "round_[1-5]|preliminary|qualifying|semifinal|final|opening|closing|shift_[1-5]";
    public static final String MAIL_RELATIVE_DAYS = "today|tomorrow|day_after_tomorrow|this_week|next_week|weekday";
    public static final String MAIL_MODES = "online|in_person";
    public static final String PERIOD_MODES = "all_day|daily_window|one_window";
    public static final String DEADLINE_KINDS = "opens|register|confirm|due";

    /**
     * One time an event or school task takes place, as the laptop found it in the email. Vietnam time. checkIn: when
     * to be there by; linkOpens: when an online event's link becomes available; endsNextDay: the end is on the next
     * day, and may be earlier than the start; relative: the day came from a word such as "ngày mai".
     */
    public record MailSession(
            @NotNull LocalDate day,
            @NotNull LocalTime start,
            LocalTime end,
            Boolean endIsApproximate,
            Boolean endsNextDay,
            LocalTime checkIn,
            LocalTime linkOpens,
            @Pattern(regexp = MAIL_MODES) String mode,
            @Pattern(regexp = MAIL_RELATIVE_DAYS) String relative,
            @Pattern(regexp = MAIL_LABELS) String label) {

        public MailSession {
            endIsApproximate = endIsApproximate != null && endIsApproximate;
            endsNextDay = endsNextDay != null && endsNextDay;
        }

        @AssertTrue(message = "end_is_approximate and ends_next_day need an end")
        boolean isEndGivenWhenMarked() {
            return end != null || !(endIsApproximate || endsNextDay);
        }

        @AssertTrue(message = "end must be after start")
        boolean isEndAfterStart() {
            return end == null || start == null || endsNextDay || end.isAfter(start);
        }

        @AssertTrue(message = "check_in and link_opens can't be after start")
        boolean isCheckInAndLinkNotAfterStart() {
            return start == null || ((checkIn == null || !checkIn.isAfter(start))
                    && (linkOpens == null || !linkOpens.isAfter(start)));
        }
    }

    /**
     * A range of days in which the student may come or do something at any time. Vietnam time. all_day: days only;
     * daily_window: fromTime to toTime each day; one_window: from fromTime on firstDay to toTime on lastDay.
     */
    public record MailPeriod(
            @NotNull LocalDate firstDay,
            @NotNull LocalDate lastDay,
            @NotNull @Pattern(regexp = PERIOD_MODES) String mode,
            LocalTime fromTime,
            LocalTime toTime,
            Boolean detailsLater,
            @Pattern(regexp = MAIL_LABELS) String label) {

        public MailPeriod {
            detailsLater = detailsLater != null && detailsLater;
        }

        @AssertTrue(message = "last_day can't be before first_day")
        boolean isLastDayNotBeforeFirst() {
            return firstDay == null || lastDay == null || !lastDay.isBefore(firstDay);
        }

        @AssertTrue(message = "an all_day Period has no times; the others have from_time and to_time, in order")
        boolean isTimesMatchingMode() {
            if (mode == null || firstDay == null || lastDay == null) {
                return true;
            }
            if (mode.equals("all_day")) {
                return fromTime == null && toTime == null;
            }
            if (fromTime == null || toTime == null) {
                return false;
            }
            return !(mode.equals("daily_window") || firstDay.equals(lastDay)) || toTime.isAfter(fromTime);
        }
    }

    /**
     * A deadline: information only, never event time. opens: registration opens; register: it closes; confirm:
     * confirming a place closes; due: something must be handed in or paid. Vietnam time.
     */
    public record MailDeadline(
            @NotNull @Pattern(regexp = DEADLINE_KINDS) String kind,
            @NotNull LocalDate day,
            LocalTime time,
            @Pattern(regexp = MAIL_MODES) String mode) {
    }

    /** What the website may know about one email: never its text. */
    public record MailItem(
            @NotNull @Pattern(regexp = "[0-9a-f]{64}") String key,
            @NotNull @Pattern(regexp = "[0-9A-F]{2,512}") String entryId,
            @Chars(max = 64) String threadId,
            @NotNull OffsetDateTime receivedAt,
            @Chars(max = 255) String senderName,
            @Chars(max = 255) String senderAddress,
            @Chars(max = 500) String subject,
            @Size(max = 2) List<@NotNull @Pattern(regexp = MAIL_CATEGORIES) String> categories,
            Boolean fromLecturer,
            @Size(max = 30) List<@NotNull LocalDate> dates,
            @Size(max = 10) List<@Valid MailSession> sessions,
            @Size(max = 5) List<@Valid MailPeriod> periods,
            @Size(max = 5) List<@Valid MailDeadline> deadlines,
            LocalDate registerBy,
            Boolean meeting,
            Boolean registered,
            @Pattern(regexp = "request|cancelled") String invitation,
            Boolean sorted,
            @Chars(max = 255) String blackboardTitle,
            @Size(max = 10) List<@Valid MailClassChange> classChanges) {

        public MailItem {
            senderName = senderName == null ? "" : senderName;
            senderAddress = senderAddress == null ? "" : senderAddress;
            subject = subject == null ? "" : subject;
            categories = categories == null ? List.of() : categories;
            fromLecturer = fromLecturer != null && fromLecturer;
            dates = dates == null ? List.of() : dates;
            sessions = sessions == null ? List.of() : sessions;
            periods = periods == null ? List.of() : periods;
            deadlines = deadlines == null ? List.of() : deadlines;
            meeting = meeting != null && meeting;
            registered = registered != null && registered;
            sorted = sorted == null || sorted;
            classChanges = classChanges == null ? List.of() : classChanges;
        }

        @AssertTrue(message = "categories must differ")
        boolean isEachCategoryOnce() {
            return new HashSet<>(categories).size() == categories.size();
        }
    }

    public record Outlook(
            @NotNull LocalDate since,
            @NotNull Boolean connected,
            @NotNull @Size(max = 2000) List<@Valid MailItem> emails) {
    }

    // ---- A whole sync -----------------------------------------------------------

    /** One part of a sync: {"status": "ok", "data": …} or {"status": "failed", "error_code": …, "error_message": …}. */
    public record Section<T extends Record>(
            @NotNull @Pattern(regexp = "ok|failed") String status,
            @Valid T data,
            @Pattern(regexp = ERROR_CODES) String errorCode,
            @Chars(min = 1, max = 500) String errorMessage) {

        @AssertTrue(message = "an ok part carries only data; a failed part carries only error_code and error_message")
        boolean isComplete() {
            if ("ok".equals(status)) {
                return data != null && errorCode == null && errorMessage == null;
            }
            return data == null && errorCode != null && errorMessage != null;
        }

        public boolean ok() {
            return "ok".equals(status);
        }
    }

    /** The result of one sync: either a whole-run error, or a result per part. */
    public record FinishRun(
            Integer schemaVersion,
            @Pattern(regexp = ERROR_CODES) String errorCode,
            @Chars(min = 1, max = 500) String errorMessage,
            @Valid Section<Timetable> timetable,
            @Valid Section<Exams> exams,
            @Valid Section<Tuition> tuition, // agents from before IUPay: accepted, never counted or saved
            @Valid Section<Iupay> iupay,
            @Valid Section<Blackboard> blackboard,
            @Valid Section<Outlook> outlook) {

        @AssertTrue(message = "schema_version must be 1")
        boolean isVersion1() {
            return schemaVersion == null || schemaVersion == 1;
        }

        @AssertTrue(message = "error_message is required with error_code")
        boolean isErrorExplained() {
            return errorCode == null || errorMessage != null;
        }

        @AssertTrue(message = "a whole-run error cannot carry section results")
        boolean isErrorWithoutSections() {
            return errorCode == null || (sections().isEmpty() && tuition == null);
        }

        @AssertTrue(message = "send either error_code or at least one section")
        boolean isErrorOrSections() {
            return errorCode != null || !sections().isEmpty();
        }

        /** The parts that were sent, by name, in the order timetable, exams, iupay, blackboard, outlook. */
        public Map<String, Section<?>> sections() {
            Map<String, Section<?>> sent = new LinkedHashMap<>();
            if (timetable != null) {
                sent.put("timetable", timetable);
            }
            if (exams != null) {
                sent.put("exams", exams);
            }
            if (iupay != null) {
                sent.put("iupay", iupay);
            }
            if (blackboard != null) {
                sent.put("blackboard", blackboard);
            }
            if (outlook != null) {
                sent.put("outlook", outlook);
            }
            return sent;
        }

        /** success, partial or failed. */
        public String overallStatus() {
            if (errorCode != null) {
                return "failed";
            }
            boolean anyOk = sections().values().stream().anyMatch(Section::ok);
            boolean anyFailed = sections().values().stream().anyMatch(section -> !section.ok());
            if (anyOk && !anyFailed) {
                return "success";
            }
            return anyOk ? "partial" : "failed";
        }
    }
}
