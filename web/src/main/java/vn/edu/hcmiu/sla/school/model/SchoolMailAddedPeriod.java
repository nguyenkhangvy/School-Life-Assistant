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
 * A Period the student added to the Timetable from Mailbox (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md,
 * 6.3): a copy of the email's Period, with the email's subject as its title, so it stays even when the email is gone.
 * It shows in the Timetable's All-day row and is never busy. Days and times are Vietnam time.
 */
@Entity
@Table(name = "school_mail_added_periods")
public class SchoolMailAddedPeriod {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "user_id", nullable = false)
    private Integer userId;

    @Column(name = "mail_key", nullable = false, length = 64)
    private String mailKey;

    @Column(name = "first_day", nullable = false)
    private LocalDate firstDay;

    @Column(name = "last_day", nullable = false)
    private LocalDate lastDay;

    @Column(nullable = false, length = 12)
    private String mode;

    @Column(name = "from_time")
    private LocalTime fromTime;

    @Column(name = "to_time")
    private LocalTime toTime;

    @Column(name = "details_later", nullable = false)
    private boolean detailsLater;

    @Column(length = 20)
    private String label;

    @Column(nullable = false, length = 500)
    private String title;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt; // UTC

    protected SchoolMailAddedPeriod() {
    }

    public SchoolMailAddedPeriod(Integer userId, String mailKey, LocalDate firstDay, LocalDate lastDay, String mode,
            LocalTime fromTime, LocalTime toTime, boolean detailsLater, String label, String title,
            LocalDateTime createdAt) {
        this.userId = userId;
        this.mailKey = mailKey;
        this.firstDay = firstDay;
        this.lastDay = lastDay;
        this.mode = mode;
        this.fromTime = fromTime;
        this.toTime = toTime;
        this.detailsLater = detailsLater;
        this.label = label;
        this.title = title;
        this.createdAt = createdAt;
    }

    /** A new, unsaved row with the same values, to save again after a try that failed. */
    public SchoolMailAddedPeriod copy() {
        return new SchoolMailAddedPeriod(userId, mailKey, firstDay, lastDay, mode, fromTime, toTime, detailsLater,
                label, title, createdAt);
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

    public LocalDate getFirstDay() {
        return firstDay;
    }

    public LocalDate getLastDay() {
        return lastDay;
    }

    public String getMode() {
        return mode;
    }

    public LocalTime getFromTime() {
        return fromTime;
    }

    public LocalTime getToTime() {
        return toTime;
    }

    public boolean isDetailsLater() {
        return detailsLater;
    }

    public String getLabel() {
        return label;
    }

    public String getTitle() {
        return title;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}
