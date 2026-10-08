package vn.edu.hcmiu.sla.school.model;

import java.time.LocalDate;
import java.time.LocalTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

/**
 * A range of days in which an email's event lets the student come or do something at any time, as the laptop found
 * it (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md, 2). mode: all_day (no times), daily_window (the
 * same hours each day) or one_window (from fromTime on the first day to toTime on the last). Vietnam time. Replaced
 * with its email at every sync.
 */
@Entity
@Table(name = "school_mail_periods")
public class SchoolMailPeriod {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "mail_id", nullable = false)
    private SchoolMail mail;

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

    protected SchoolMailPeriod() {
    }

    public SchoolMailPeriod(SchoolMail mail, LocalDate firstDay, LocalDate lastDay, String mode, LocalTime fromTime,
            LocalTime toTime, boolean detailsLater, String label) {
        this.mail = mail;
        this.firstDay = firstDay;
        this.lastDay = lastDay;
        this.mode = mode;
        this.fromTime = fromTime;
        this.toTime = toTime;
        this.detailsLater = detailsLater;
        this.label = label;
    }

    public Integer getId() {
        return id;
    }

    public SchoolMail getMail() {
        return mail;
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
}
