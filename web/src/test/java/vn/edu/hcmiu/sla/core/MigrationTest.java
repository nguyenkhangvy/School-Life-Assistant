package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

import javax.sql.DataSource;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.springframework.jdbc.datasource.init.ScriptUtils;

/** On an empty database (a teammate's laptop), Flyway's V1 creates every table the Python site had. */
@SpringBootTest
class MigrationTest {

    @Autowired
    DataSource dataSource;

    static Set<String> tables(DataSource database) throws Exception {
        Set<String> tables = new HashSet<>();
        try (Connection connection = database.getConnection();
             ResultSet rows = connection.getMetaData().getTables(connection.getCatalog(), null, "%", new String[] {"TABLE"})) {
            while (rows.next()) {
                tables.add(rows.getString("TABLE_NAME").toLowerCase(Locale.ROOT));
            }
        }
        return tables;
    }

    @Test
    void anEmptyDatabaseGetsEveryTable() throws Exception {
        assertThat(tables(dataSource)).contains(
                "users", "school_sync_devices", "school_sync_settings", "school_sync_runs", "school_changes",
                "school_courses", "school_class_meetings", "school_exams", "school_events",
                "school_bb_courses", "school_bb_announcements", "school_bb_assignments", "school_bb_materials",
                "school_mail", "school_mail_changes", "school_mail_choices", "school_mail_status", "school_mail_sessions",
                "school_mail_settings", "school_mail_joined", "school_tuition_bills", "school_tuition_status", "school_my_events", "school_my_event_skips",
                "school_mail_periods", "school_mail_deadlines", "school_mail_added_periods",
                "social_friendships",
                "flyway_schema_history");
        assertThat(tables(dataSource)).doesNotContain("school_tuition");
    }

    /** Like the student's database: every table the Python site made (V1's), and Alembic's alembic_version. */
    static DataSource pythonMadeDatabase() throws Exception {
        DriverManagerDataSource database = new DriverManagerDataSource(
                "jdbc:h2:mem:python-made-" + UUID.randomUUID() + ";MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
                "sa", "");
        try (Connection connection = database.getConnection(); Statement sql = connection.createStatement()) {
            ScriptUtils.executeSqlScript(connection, new ClassPathResource("db/migration/V1__baseline.sql"));
            sql.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num))");
            sql.execute("INSERT INTO alembic_version VALUES ('7d2f4b9c1e30')");
        }
        return database;
    }

    /** The site's own Flyway settings: record V1 as done on an existing database, then run what is newer. */
    static void migrate(DataSource database, String... locations) {
        Flyway.configure().dataSource(database).locations(locations).baselineOnMigrate(true).baselineVersion("1")
                .outOfOrder(true).load().migrate();
    }

    @Test
    void theSwitchRemovesAlembicsTableFromTheDatabaseThePythonSiteMade() throws Exception {
        DataSource pythonMade = pythonMadeDatabase();

        migrate(pythonMade, "classpath:db/migration");

        assertThat(tables(pythonMade)).contains("flyway_schema_history").doesNotContain("alembic_version");
    }

    @Test
    void laterMigrationsWorkOnTheDatabaseThePythonSiteMade() throws Exception {
        // db/later (test files only) has a later migration: a new table with a key to users.
        DataSource pythonMade = pythonMadeDatabase();

        migrate(pythonMade, "classpath:db/migration", "classpath:db/later");

        assertThat(tables(pythonMade)).contains("later_items");
    }

    @Test
    void aMailSettingsRowWithoutAutoDoneHasItOn() throws Exception {
        // No row means auto-Done is on; a row written without the column means the same.
        SingleConnectionDataSource fresh = freshWithTwoAccounts();
        try (Statement sql = fresh.getConnection().createStatement()) {
            sql.execute("INSERT INTO school_mail_settings (user_id) VALUES (1)");
            try (ResultSet row = sql.executeQuery("SELECT auto_done FROM school_mail_settings WHERE user_id = 1")) {
                assertThat(row.next()).isTrue();
                assertThat(row.getBoolean("auto_done")).isTrue();
            }
        } finally {
            fresh.destroy();
        }
    }

    @Test
    void theBaselineLeavesKeyNamesToMysqlLikeAlembicDid() throws Exception {
        // The student's database got MySQL's own names (email, user_id, school_courses_ibfk_1, ...). Unnamed keys
        // give a Flyway-made database the same names, so a later migration that changes a key by name works on both.
        String baseline = new ClassPathResource("db/migration/V1__baseline.sql").getContentAsString(StandardCharsets.UTF_8);

        assertThat(baseline).doesNotContain("CONSTRAINT");
    }

    @Test
    void accountsMadeBeforeRolesBecomeActiveStudents() throws Exception {
        // The live site's accounts were made before module 0: each becomes an active Student, last changed when made.
        // One connection for everything, so H2 keeps the role CHECK (see freshWithTwoAccounts).
        SingleConnectionDataSource live = new SingleConnectionDataSource(
                "jdbc:h2:mem:live-" + UUID.randomUUID() + ";MODE=MySQL;DATABASE_TO_LOWER=TRUE", "sa", "", true);
        try {
            ScriptUtils.executeSqlScript(live.getConnection(), new ClassPathResource("db/migration/V1__baseline.sql"));
            try (Statement sql = live.getConnection().createStatement()) {
                sql.execute("INSERT INTO users (id, email, display_name, password_hash, created_at)"
                        + " VALUES (1, 'an@example.com', 'An', 'x', '2026-09-01 08:00:00')");
            }

            migrate(live, "classpath:db/migration");

            try (Statement sql = live.getConnection().createStatement();
                 ResultSet row = sql.executeQuery("SELECT role, created_at, updated_at, updated_by, deactivated_at,"
                         + " last_login_at, must_change_password FROM users WHERE id = 1")) {
                assertThat(row.next()).isTrue();
                assertThat(row.getString("role")).isEqualTo("student");
                assertThat(row.getTimestamp("updated_at")).isEqualTo(row.getTimestamp("created_at"));
                assertThat(row.getObject("updated_by")).isNull();
                assertThat(row.getTimestamp("deactivated_at")).isNull();
                assertThat(row.getTimestamp("last_login_at")).isNull();
                assertThat(row.getBoolean("must_change_password")).isFalse();
            }
        } finally {
            live.destroy();
        }
    }

    /**
     * A database made by every migration, with two accounts: ids 1 (An) and 2 (Binh). Flyway and the test share one
     * connection that is never closed: H2 2.4 loses a CHECK's list of values (status IN (...)) once the connection
     * that created the table closes, and then refuses every row ("Check constraint invalid"). MySQL doesn't, and
     * the site's own tests keep Flyway's connection open in the pool. Call destroy() when done, which closes it.
     */
    static SingleConnectionDataSource freshWithTwoAccounts() throws Exception {
        SingleConnectionDataSource fresh = new SingleConnectionDataSource(
                "jdbc:h2:mem:fresh-" + UUID.randomUUID() + ";MODE=MySQL;DATABASE_TO_LOWER=TRUE", "sa", "", true);
        migrate(fresh, "classpath:db/migration");
        try (Connection connection = fresh.getConnection(); Statement sql = connection.createStatement()) {
            sql.execute("INSERT INTO users (id, email, display_name, password_hash, created_at, updated_at)"
                    + " VALUES (1, 'an@example.com', 'An', 'x', '2026-10-06 08:00:00', '2026-10-06 08:00:00')");
            sql.execute("INSERT INTO users (id, email, display_name, password_hash, created_at, updated_at)"
                    + " VALUES (2, 'binh@example.com', 'Binh', 'x', '2026-10-06 08:00:00', '2026-10-06 08:00:00')");
        }
        return fresh;
    }

    static final String FRIENDSHIP = "INSERT INTO social_friendships"
            + " (user_low_id, user_high_id, requested_by_id, status, created_at, accepted_at) VALUES ";

    @ParameterizedTest
    @ValueSource(strings = {
        "(1, 2, 1, 'blocked', '2026-10-06 08:00:00', NULL)",                   // not a status
        "(1, 2, 1, 'accepted', '2026-10-06 08:00:00', NULL)",                  // accepted, but no time
        "(1, 2, 1, 'pending', '2026-10-06 08:00:00', '2026-10-06 09:00:00')"}) // a time, but still pending
    void theFriendshipsTableRefusesBadRows(String values) throws Exception {
        SingleConnectionDataSource database = freshWithTwoAccounts();
        try (Statement sql = database.getConnection().createStatement()) {
            assertThatThrownBy(() -> sql.execute(FRIENDSHIP + values)).isInstanceOf(SQLException.class)
                    .hasMessageContaining("Check constraint violation");
        } finally {
            database.destroy();
        }
    }

    @Test
    void twoStudentsHaveOneFriendshipRow() throws Exception {
        SingleConnectionDataSource database = freshWithTwoAccounts();
        try (Statement sql = database.getConnection().createStatement()) {
            sql.execute(FRIENDSHIP + "(1, 2, 1, 'pending', '2026-10-06 08:00:00', NULL)");

            assertThatThrownBy(() -> sql.execute(FRIENDSHIP + "(1, 2, 2, 'pending', '2026-10-06 08:05:00', NULL)"))
                    .isInstanceOfSatisfying(SQLException.class,
                            duplicate -> assertThat(duplicate.getSQLState()).isEqualTo("23505")); // unique key
        } finally {
            database.destroy();
        }
    }
}
