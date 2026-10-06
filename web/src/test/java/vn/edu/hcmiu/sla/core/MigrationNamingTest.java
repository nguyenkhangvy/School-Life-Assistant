package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.regex.Pattern;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

/** Migrations are named V&lt;date&gt;_&lt;module&gt;_&lt;number&gt;__&lt;what&gt;.sql: module 1 is School, 2 is Social. */
class MigrationNamingTest {

    static final Pattern NAME = Pattern.compile("V\\d{8}_[12]_\\d+__[a-z0-9_]+\\.sql");

    @Test
    void everyMigrationIsNamedByDateModuleAndNumber() throws Exception {
        Resource[] files = new PathMatchingResourcePatternResolver().getResources("classpath*:db/migration/*");

        assertThat(files).isNotEmpty();
        for (Resource file : files) {
            String name = file.getFilename();
            assertThat(name.equals("V1__baseline.sql") || NAME.matcher(name).matches())
                    .as("%s should be named like V20261001_1_1__new_table.sql "
                            + "(date, module: 1 School, 2 Social, then a number)", name)
                    .isTrue();
        }
    }

    @Test
    void theModulesAreSchoolAndSocial() {
        assertThat(NAME.matcher("V20261006_1_1__school_table.sql").matches()).isTrue();
        assertThat(NAME.matcher("V20261006_2_1__social_friendships.sql").matches()).isTrue();
        assertThat(NAME.matcher("V20261006_3_1__expense_table.sql").matches()).isFalse();
    }
}
