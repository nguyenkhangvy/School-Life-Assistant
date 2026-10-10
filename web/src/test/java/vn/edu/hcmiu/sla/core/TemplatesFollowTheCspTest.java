package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

/**
 * The site's Content-Security-Policy refuses inline scripts, inline event handlers and style attributes (security
 * hardening spec, 5), and a browser does so silently, on the live site only. So no template may contain them: scripts
 * are files in static/js.
 */
class TemplatesFollowTheCspTest {

    @Test
    void noTemplateHasInlineCodeTheCspWouldRefuse() throws Exception {
        Resource[] templates = new PathMatchingResourcePatternResolver().getResources("classpath*:templates/**/*.html");

        assertThat(templates).isNotEmpty();
        for (Resource template : templates) {
            String html = template.getContentAsString(StandardCharsets.UTF_8);
            String name = template.getFilename();
            assertThat(html).as("%s: a <script> without src", name).doesNotContainPattern("<script(?![^>]*\\bsrc\\s*=)[^>]*>");
            assertThat(html).as("%s: an on…= event handler", name).doesNotContainPattern("\\s(th:)?on[a-z]+\\s*=");
            assertThat(html).as("%s: a style= attribute", name).doesNotContainPattern("\\s(th:)?style\\s*=");
        }
    }
}
