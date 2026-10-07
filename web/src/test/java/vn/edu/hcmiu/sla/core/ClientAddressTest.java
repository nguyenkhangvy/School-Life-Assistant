package vn.edu.hcmiu.sla.core;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

/** The visitor's address for limits (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.2). */
class ClientAddressTest {

    @Test
    void anIpv4AddressIsKeptAsItIs() {
        assertThat(ClientAddress.of("203.0.113.7")).isEqualTo("203.0.113.7");
    }

    @Test
    void ipv6IsGroupedByItsFirst64Bits() {
        assertThat(ClientAddress.of("2001:db8:1:2:aaaa:bbbb:cccc:dddd")).isEqualTo("2001:db8:1:2::/64");
        assertThat(ClientAddress.of("2001:0db8:0001:0002::1")).isEqualTo("2001:db8:1:2::/64");
        assertThat(ClientAddress.of("2001:db8:1:3::1")).isEqualTo("2001:db8:1:3::/64");
        assertThat(ClientAddress.of("::1")).isEqualTo("0:0:0:0::/64");
    }

    @Test
    void anIpv4AddressWrittenAsIpv6CountsAsTheIpv4Address() { // Review Focus
        assertThat(ClientAddress.of("::ffff:203.0.113.7")).isEqualTo("203.0.113.7");
    }

    @Test
    void theRequestsRemoteAddressIsUsed() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setRemoteAddr("2001:db8:1:2::5");

        assertThat(ClientAddress.of(request)).isEqualTo("2001:db8:1:2::/64");
    }
}
