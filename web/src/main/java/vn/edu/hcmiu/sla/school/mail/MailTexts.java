package vn.edu.hcmiu.sla.school.mail;

import java.time.LocalDate;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.time.format.TextStyle;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import vn.edu.hcmiu.sla.school.VietnamTime;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Deadline;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Period;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Session;

/**
 * How the laptop's codes and times read on the site (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md,
 * 3.2 and 6.2). The codes come from fixed lists, so every text here is the site's own, never the email's. Pure
 * functions.
 */
public final class MailTexts {

    private MailTexts() {
    }

    private static final DateTimeFormatter CLOCK = DateTimeFormatter.ofPattern("HH:mm");

    static final Map<String, String> LABELS = labels();
    static final Map<String, String> MODES = Map.of("online", "Online", "in_person", "In person");

    private static Map<String, String> labels() {
        Map<String, String> names = new LinkedHashMap<>();
        for (int n = 1; n <= 5; n++) {
            names.put("round_" + n, "Round " + n);
            names.put("shift_" + n, "Shift " + n);
        }
        names.put("preliminary", "Preliminary round");
        names.put("qualifying", "Qualifying round");
        names.put("semifinal", "Semi-final");
        names.put("final", "Final");
        names.put("opening", "Opening");
        names.put("closing", "Closing");
        return Map.copyOf(names);
    }

    /** "Round 1" for round_1; null for none or a code the site doesn't know. */
    public static String label(String code) {
        return code == null ? null : LABELS.get(code);
    }

    /** "Online" or "In person"; null for none. */
    public static String mode(String code) {
        return code == null ? null : MODES.get(code);
    }

    /** The word a relative day was read from: "tomorrow", "this Thursday", "Thursday" (day: the session's day). */
    public static String relative(String code, LocalDate day) {
        if (code == null) {
            return null;
        }
        String weekday = day.getDayOfWeek().getDisplayName(TextStyle.FULL, Locale.ENGLISH);
        return switch (code) {
            case "today" -> "today";
            case "tomorrow" -> "tomorrow";
            case "day_after_tomorrow" -> "the day after tomorrow";
            case "this_week" -> "this " + weekday;
            case "next_week" -> "next " + weekday;
            case "weekday" -> weekday;
            default -> null;
        };
    }

    static String clock(LocalTime time) {
        return CLOCK.format(time);
    }

    /**
     * "Tue 29/09 13:00–14:00", "Tue 29/09 13:00–~14:00" (an approximate end), "Thu 31/12 22:00 – Fri 01/01 00:30"
     * (an end on the next day) or "Thu 01/10 from 14:00", then what else is known: "· check-in 13:30", "· Online",
     * "· link from 09:00", "· from 'tomorrow'" and the label.
     */
    public static String session(Session s) {
        String start = clock(s.start());
        String approximately = s.endIsApproximate() ? "~" : "";
        StringBuilder text = new StringBuilder(VietnamTime.dayLabel(s.day())).append(' ');
        if (s.end() == null) {
            text.append("from ").append(start);
        } else if (s.endsNextDay()) {
            text.append(start).append(" – ").append(VietnamTime.dayLabel(s.day().plusDays(1))).append(' ')
                    .append(approximately).append(clock(s.end()));
        } else {
            text.append(start).append('–').append(approximately).append(clock(s.end()));
        }
        List<String> more = new ArrayList<>();
        if (s.checkIn() != null) {
            more.add("check-in " + clock(s.checkIn()));
        }
        if (mode(s.mode()) != null) {
            more.add(mode(s.mode()));
        }
        if (s.linkOpens() != null) {
            more.add("link from " + clock(s.linkOpens()));
        }
        if (relative(s.relative(), s.day()) != null) {
            more.add("from '" + relative(s.relative(), s.day()) + "'");
        }
        if (label(s.label()) != null) {
            more.add(label(s.label()));
        }
        more.forEach(part -> text.append(" · ").append(part));
        return text.toString();
    }

    /**
     * "Period · Mon 02/11 → Thu 05/11 · 09:00–17:00 each day", "Period · Mon 26/10 → Fri 30/10 · all day",
     * "Period · Sat 28/11 09:00 → Sun 29/11 16:00" or "Period · Sat 14/11 · 08:00–16:00", then "· your own time comes
     * later" and the label.
     */
    public static String period(Period p) {
        boolean oneDay = p.firstDay().equals(p.lastDay());
        String days = oneDay ? VietnamTime.dayLabel(p.firstDay())
                : VietnamTime.dayLabel(p.firstDay()) + " → " + VietnamTime.dayLabel(p.lastDay());
        StringBuilder text = new StringBuilder("Period · ");
        if (p.allDay()) {
            text.append(days).append(" · all day");
        } else if (oneDay) {
            text.append(days).append(" · ").append(clock(p.fromTime())).append('–').append(clock(p.toTime()));
        } else if (p.mode().equals("daily_window")) {
            text.append(days).append(" · ").append(clock(p.fromTime())).append('–').append(clock(p.toTime()))
                    .append(" each day");
        } else {
            text.append(VietnamTime.dayLabel(p.firstDay())).append(' ').append(clock(p.fromTime())).append(" → ")
                    .append(VietnamTime.dayLabel(p.lastDay())).append(' ').append(clock(p.toTime()));
        }
        if (p.detailsLater()) {
            text.append(" · your own time comes later");
        }
        if (label(p.label()) != null) {
            text.append(" · ").append(label(p.label()));
        }
        return text.toString();
    }

    /**
     * An added Period's hours on the Timetable: "09:00–17:00 each day", "09:00 Sat until 16:00 Sun", "08:00–16:00", or
     * null all day.
     */
    public static String periodHours(Period p) {
        if (p.allDay()) {
            return null;
        }
        String hours = clock(p.fromTime()) + "–" + clock(p.toTime());
        if (p.firstDay().equals(p.lastDay())) {
            return hours;
        }
        if (p.mode().equals("daily_window")) {
            return hours + " each day";
        }
        return clock(p.fromTime()) + " " + weekday(p.firstDay()) + " until " + clock(p.toTime()) + " "
                + weekday(p.lastDay());
    }

    private static String weekday(LocalDate day) {
        return day.getDayOfWeek().getDisplayName(TextStyle.SHORT, Locale.ENGLISH);
    }

    /** "17:00 Mon 12/10", or "Mon 12/10" without a time. */
    static String when(Deadline d) {
        return (d.time() != null ? clock(d.time()) + " " : "") + VietnamTime.dayLabel(d.day());
    }

    /**
     * One deadline as the Join page lists it: "Registration opens 08:00 Thu 08/10", "Register by Sat 10/10 · In
     * person", "Confirm by Thu 15/10" or "Due 23:59 Sun 18/10".
     */
    public static String deadline(Deadline d) {
        String what = switch (d.kind()) {
            case "opens" -> "Registration opens ";
            case "register" -> "Register by ";
            case "confirm" -> "Confirm by ";
            default -> "Due ";
        };
        return what + when(d) + (mode(d.mode()) != null ? " · " + mode(d.mode()) : "");
    }
}
