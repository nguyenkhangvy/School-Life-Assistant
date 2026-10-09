package vn.edu.hcmiu.sla.school.model;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * An event session the student joined from Mailbox. Day and times are Vietnam time; end may be empty, and is on the
 * next day when endsNextDay. The email's subject is copied in as the title, and the session's check-in, mode and end
 * with it, so it stays in the Timetable as it was even when the email is gone.
 */
@Entity
@Table(name = "school_mail_joined")
public class SchoolMailJoined {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "user_id", nullable = false)
    private Integer userId;

    @Column(name = "mail_key", nullable = false, length = 64)
    private String mailKey;

    @Column(name = "session_day", nullable = false)
    private LocalDate day;

    @Column(name = "start_time", nullable = false)
    private LocalTime start;

    @Column(name = "end_time")
    private LocalTime end;

    @Column(nullable = false, length = 500)
    private String title;

    @Column(length = 100)
    private String place;

    @Column(name = "training_points", nullable = false)
    private boolean trainingPoints;

    @Column(name = "by_hand", nullable = false)
    private boolean byHand;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt; // UTC

    @Column(name = "check_in")
    private LocalTime checkIn;

    @Column(length = 10)
    private String mode;

    @Column(name = "end_is_approximate", nullable = false)
    private boolean endIsApproximate;

    @Column(name = "ends_next_day", nullable = false)
    private boolean endsNextDay;

    protected SchoolMailJoined() {
    }

    public SchoolMailJoined(Integer userId, String mailKey, LocalDate day, LocalTime start, LocalTime end, String title,
            String place, boolean trainingPoints, boolean byHand, LocalDateTime createdAt) {
        this.userId = userId;
        this.mailKey = mailKey;
        this.day = day;
        this.start = start;
        this.end = end;
        this.title = title;
        this.place = place;
        this.trainingPoints = trainingPoints;
        this.byHand = byHand;
        this.createdAt = createdAt;
    }

    /** The found session's check-in, mode and end details, kept with the joined copy. Returns this row. */
    public SchoolMailJoined keeping(LocalTime checkIn, String mode, boolean endIsApproximate, boolean endsNextDay) {
        this.checkIn = checkIn;
        this.mode = mode;
        this.endIsApproximate = endIsApproximate;
        this.endsNextDay = endsNextDay;
        return this;
    }

    /** A new, unsaved row with the same values, to save again after a try that failed. */
    public SchoolMailJoined copy() {
        return new SchoolMailJoined(userId, mailKey, day, start, end, title, place, trainingPoints, byHand, createdAt)
                .keeping(checkIn, mode, endIsApproximate, endsNextDay);
    }

    public Integer getId() {
        return id;
    }

    public Integer getUserId() {
        return userId;
    }

    public String getMailKey() {
        return mailKey;
    }

    public LocalDate getDay() {
        return day;
    }

    public LocalTime getStart() {
        return start;
    }

    public LocalTime getEnd() {
        return end;
    }

    public String getTitle() {
        return title;
    }

    public String getPlace() {
        return place;
    }

    public boolean isTrainingPoints() {
        return trainingPoints;
    }

    public boolean isByHand() {
        return byHand;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public LocalTime getCheckIn() {
        return checkIn;
    }

    public String getMode() {
        return mode;
    }

    public boolean isEndIsApproximate() {
        return endIsApproximate;
    }

    public boolean isEndsNextDay() {
        return endsNextDay;
    }
}
