-- Friend requests and friends (docs/superpowers/specs/2026-10-06-friends-and-groups-design.md, section 3.1).
-- One row per pair of students, the smaller user id first, whichever way the request went. Declining, cancelling
-- and removing delete the row. MySQL refuses a CHECK on a column whose foreign key has an ON DELETE action, so
-- "smaller id first" and "requested_by is one of the two" are kept by SocialFriendship, not by CHECKs here.
CREATE TABLE social_friendships (
    id INT NOT NULL AUTO_INCREMENT,
    user_low_id INT NOT NULL,
    user_high_id INT NOT NULL,
    requested_by_id INT NOT NULL,
    status VARCHAR(8) NOT NULL,
    created_at DATETIME NOT NULL,
    accepted_at DATETIME NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_social_friendships_pair UNIQUE (user_low_id, user_high_id),
    CONSTRAINT ck_social_friendships_status CHECK (status IN ('pending', 'accepted')),
    CONSTRAINT ck_social_friendships_accepted CHECK ((status = 'accepted') = (accepted_at IS NOT NULL)),
    CONSTRAINT fk_social_friendships_low FOREIGN KEY (user_low_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_social_friendships_high FOREIGN KEY (user_high_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_social_friendships_by FOREIGN KEY (requested_by_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_social_friendships_high ON social_friendships (user_high_id);
