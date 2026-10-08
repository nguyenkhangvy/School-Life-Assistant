package vn.edu.hcmiu.sla.school.pages;

import java.util.ArrayList;
import java.util.List;

/**
 * Join…: the sessions ticked (by MailSessions.Line.id, e.g. "2026-09-29T13:30"), the Periods ticked (by
 * Mailbox.Period.id, e.g. "2026-11-02/2026-11-05/daily_window/09:00"), one session added by hand (day, start and an
 * optional end; day "" means none), and an optional place.
 */
public class JoinForm {

    private List<String> sessions = new ArrayList<>();
    private List<String> periods = new ArrayList<>();
    private String day = "";
    private String start = "";
    private String end = "";
    private String place = "";

    public JoinForm() {
    }

    JoinForm(List<String> sessions, List<String> periods, String place) {
        this.sessions = new ArrayList<>(sessions);
        this.periods = new ArrayList<>(periods);
        this.place = place;
    }

    public List<String> getSessions() {
        return sessions;
    }

    public void setSessions(List<String> sessions) {
        this.sessions = sessions == null ? new ArrayList<>() : sessions;
    }

    public List<String> getPeriods() {
        return periods;
    }

    public void setPeriods(List<String> periods) {
        this.periods = periods == null ? new ArrayList<>() : periods;
    }

    public String getDay() {
        return day;
    }

    public void setDay(String day) {
        this.day = day == null ? "" : day.strip();
    }

    public String getStart() {
        return start;
    }

    public void setStart(String start) {
        this.start = start == null ? "" : start.strip();
    }

    public String getEnd() {
        return end;
    }

    public void setEnd(String end) {
        this.end = end == null ? "" : end.strip();
    }

    public String getPlace() {
        return place;
    }

    public void setPlace(String place) {
        this.place = place == null ? "" : place.strip();
    }
}
