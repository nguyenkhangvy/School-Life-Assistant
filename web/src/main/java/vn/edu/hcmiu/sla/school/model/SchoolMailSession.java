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
 * One time an email's event or school task takes place, as the laptop found it in the email. Day and times are
 * Vietnam time; end may be empty, and is on the next day when endsNextDay. checkIn: when to be there by; linkOpens:
 * when an online event's link becomes available; mode, relativeDay and label are codes from the upload format's lists
 * (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md, 3). Replaced with its email at every sync.
 */
@Entity
@Table(name = "school_mail_sessions")
public class SchoolMailSession {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "mail_id", nullable = false)
    private SchoolMail mail;

    @Column(name = "session_day", nullable = false)
    private LocalDate day;

    @Column(name = "start_time", nullable = false)
    private LocalTime start;

    @Column(name = "end_time")
    private LocalTime end;

    @Column(name = "end_is_approximate", nullable = false)
    private boolean endIsApproximate;

    @Column(name = "ends_next_day", nullable = false)
    private boolean endsNextDay;

    @Column(name = "check_in")
    private LocalTime checkIn;

    @Column(name = "link_opens")
    private LocalTime linkOpens;

    @Column(length = 10)
    private String mode;

    @Column(name = "relative_day", length = 20)
    private String relativeDay;

    @Column(length = 20)
    private String label;

    protected SchoolMailSession() {
    }

    public SchoolMailSession(SchoolMail mail, LocalDate day, LocalTime start, LocalTime end) {
        this(mail, day, start, end, false, false, null, null, null, null, null);
    }

    public SchoolMailSession(SchoolMail mail, LocalDate day, LocalTime start, LocalTime end, boolean endIsApproximate,
            boolean endsNextDay, LocalTime checkIn, LocalTime linkOpens, String mode, String relativeDay, String label) {
        this.mail = mail;
        this.day = day;
        this.start = start;
        this.end = end;
        this.endIsApproximate = endIsApproximate;
        this.endsNextDay = endsNextDay;
        this.checkIn = checkIn;
        this.linkOpens = linkOpens;
        this.mode = mode;
        this.relativeDay = relativeDay;
        this.label = label;
    }

    public Integer getId() {
        return id;
    }

    public SchoolMail getMail() {
        return mail;
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

    public boolean isEndIsApproximate() {
        return endIsApproximate;
    }

    public boolean isEndsNextDay() {
        return endsNextDay;
    }

    public LocalTime getCheckIn() {
        return checkIn;
    }

    public LocalTime getLinkOpens() {
        return linkOpens;
    }

    public String getMode() {
        return mode;
    }

    public String getRelativeDay() {
        return relativeDay;
    }

    public String getLabel() {
        return label;
    }
}
