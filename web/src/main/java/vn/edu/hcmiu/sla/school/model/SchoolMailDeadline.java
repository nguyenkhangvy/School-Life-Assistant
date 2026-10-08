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
 * A deadline the laptop found in an email: information only, never event time
 * (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md, 2). kind: opens (registration opens), register (it
 * closes), confirm or due; mode: online, in_person or none. Day and time are Vietnam time; time may be empty.
 * Replaced with its email at every sync.
 */
@Entity
@Table(name = "school_mail_deadlines")
public class SchoolMailDeadline {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "mail_id", nullable = false)
    private SchoolMail mail;

    @Column(nullable = false, length = 10)
    private String kind;

    @Column(name = "deadline_day", nullable = false)
    private LocalDate day;

    @Column(name = "deadline_time")
    private LocalTime time;

    @Column(length = 10)
    private String mode;

    protected SchoolMailDeadline() {
    }

    public SchoolMailDeadline(SchoolMail mail, String kind, LocalDate day, LocalTime time, String mode) {
        this.mail = mail;
        this.kind = kind;
        this.day = day;
        this.time = time;
        this.mode = mode;
    }

    public Integer getId() {
        return id;
    }

    public SchoolMail getMail() {
        return mail;
    }

    public String getKind() {
        return kind;
    }

    public LocalDate getDay() {
        return day;
    }

    public LocalTime getTime() {
        return time;
    }

    public String getMode() {
        return mode;
    }
}
