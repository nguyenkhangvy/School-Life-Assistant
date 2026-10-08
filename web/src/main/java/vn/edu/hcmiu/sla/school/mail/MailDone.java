package vn.edu.hcmiu.sla.school.mail;

import java.time.Clock;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import vn.edu.hcmiu.sla.school.VietnamTime;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Card;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Found;
import vn.edu.hcmiu.sla.school.mail.Mailbox.Mine;
import vn.edu.hcmiu.sla.school.model.SchoolMailChoice;
import vn.edu.hcmiu.sla.school.model.SchoolMailChoiceRepository;
import vn.edu.hcmiu.sla.school.model.SchoolMailRepository;

/**
 * Which of the student's emails are on a card they marked Done, as Mailbox groups them: an added Period is hidden
 * from the Timetable while its card is Done (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md, 6.5).
 */
@Service
public class MailDone {

    private final Clock clock;
    private final SchoolMailRepository mails;
    private final SchoolMailChoiceRepository choices;

    public MailDone(Clock clock, SchoolMailRepository mails, SchoolMailChoiceRepository choices) {
        this.clock = clock;
        this.mails = mails;
        this.choices = choices;
    }

    /** The keys of every email on one of the student's Done cards. */
    @Transactional(readOnly = true)
    public Set<String> keys(Integer userId) {
        Map<String, SchoolMailChoice> byKey = choices.findByUserId(userId).stream()
                .collect(Collectors.toMap(SchoolMailChoice::getMailKey, Function.identity()));
        if (byKey.values().stream().noneMatch(SchoolMailChoice::isDone)) {
            return Set.of();
        }
        LocalDateTime now = VietnamTime.of(LocalDateTime.now(clock)).toLocalDateTime();
        return Mailbox.build(mails.findByUserIdOrderByReceivedAtDescIdDesc(userId), byKey,
                        new Found(Map.of(), Map.of(), Map.of()), Mine.NOTHING, now)
                .done().stream().map(Card::keys).flatMap(keys -> keys.stream()).collect(Collectors.toSet());
    }
}
