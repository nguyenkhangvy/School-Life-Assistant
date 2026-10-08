-- Mailbox, round three: each session's check-in, link, mode, end and label; Periods; every deadline; the meeting and
-- registered flags and Outlook invitations; joined sessions keep their check-in, mode and end; the Periods the student
-- added (docs/superpowers/specs/2026-10-07-mail-event-kinds-design.md, section 6.1). Deadlines' days and times are
-- stored in deadline_day and deadline_time (day is a reserved word).
ALTER TABLE school_mail ADD COLUMN meeting BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE school_mail ADD COLUMN registered BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE school_mail ADD COLUMN invitation VARCHAR(10) NULL;

ALTER TABLE school_mail_sessions ADD COLUMN check_in TIME NULL;
ALTER TABLE school_mail_sessions ADD COLUMN link_opens TIME NULL;
ALTER TABLE school_mail_sessions ADD COLUMN end_is_approximate BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE school_mail_sessions ADD COLUMN ends_next_day BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE school_mail_sessions ADD COLUMN mode VARCHAR(10) NULL;
ALTER TABLE school_mail_sessions ADD COLUMN relative_day VARCHAR(20) NULL;
ALTER TABLE school_mail_sessions ADD COLUMN label VARCHAR(20) NULL;

-- Replaced with their email at every sync, like sessions.
CREATE TABLE school_mail_periods (
    id INT NOT NULL AUTO_INCREMENT,
    mail_id INT NOT NULL,
    first_day DATE NOT NULL,
    last_day DATE NOT NULL,
    mode VARCHAR(12) NOT NULL,
    from_time TIME NULL,
    to_time TIME NULL,
    details_later BOOLEAN NOT NULL,
    label VARCHAR(20) NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_school_mail_periods_mail FOREIGN KEY (mail_id) REFERENCES school_mail (id) ON DELETE CASCADE
);

CREATE TABLE school_mail_deadlines (
    id INT NOT NULL AUTO_INCREMENT,
    mail_id INT NOT NULL,
    kind VARCHAR(10) NOT NULL,
    deadline_day DATE NOT NULL,
    deadline_time TIME NULL,
    mode VARCHAR(10) NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_school_mail_deadlines_mail FOREIGN KEY (mail_id) REFERENCES school_mail (id) ON DELETE CASCADE
);

ALTER TABLE school_mail_joined ADD COLUMN check_in TIME NULL;
ALTER TABLE school_mail_joined ADD COLUMN mode VARCHAR(10) NULL;
ALTER TABLE school_mail_joined ADD COLUMN end_is_approximate BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE school_mail_joined ADD COLUMN ends_next_day BOOLEAN NOT NULL DEFAULT FALSE;

-- The Periods the student added to the Timetable. A sync never touches them, so they stay even when their email is
-- gone, like joined sessions. from_time is part of the key: one email can give two daily windows over the same days
-- ("8h00 - 11h30 & 13h00 - 16h00 (Từ nay đến 20/09)").
CREATE TABLE school_mail_added_periods (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    mail_key VARCHAR(64) NOT NULL,
    first_day DATE NOT NULL,
    last_day DATE NOT NULL,
    mode VARCHAR(12) NOT NULL,
    from_time TIME NULL,
    to_time TIME NULL,
    details_later BOOLEAN NOT NULL,
    label VARCHAR(20) NULL,
    title VARCHAR(500) NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_school_mail_added_periods UNIQUE (user_id, mail_key, first_day, last_day, mode, from_time),
    CONSTRAINT fk_school_mail_added_periods_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
