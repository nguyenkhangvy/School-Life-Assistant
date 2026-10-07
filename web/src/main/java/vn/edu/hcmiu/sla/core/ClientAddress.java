package vn.edu.hcmiu.sla.core;

import java.net.Inet6Address;
import java.net.InetAddress;
import java.net.UnknownHostException;

import jakarta.servlet.http.HttpServletRequest;

/**
 * The visitor's address for limits (docs/superpowers/specs/2026-10-07-security-hardening-design.md, 3.2). On the server,
 * request.getRemoteAddr() is the visitor's: Caddy sets X-Forwarded-For, the site reads it
 * (SERVER_FORWARD_HEADERS_STRATEGY=framework), and only Caddy can reach the site. IPv4 is kept as it is; IPv6 is
 * grouped by its first 64 bits, so one device can't get round a limit by changing its IPv6 address.
 */
public final class ClientAddress {

    private ClientAddress() {
    }

    public static String of(HttpServletRequest request) {
        return of(request.getRemoteAddr());
    }

    static String of(String address) {
        if (address == null || !address.contains(":")) {
            return String.valueOf(address);
        }
        try {
            InetAddress parsed = InetAddress.getByName(address); // an IPv6 literal: parsed, never looked up
            if (!(parsed instanceof Inet6Address)) {
                return parsed.getHostAddress(); // ::ffff:203.0.113.7 is an IPv4 address
            }
            byte[] bytes = parsed.getAddress();
            return String.format("%x:%x:%x:%x::/64", word(bytes, 0), word(bytes, 2), word(bytes, 4), word(bytes, 6));
        } catch (UnknownHostException notAnAddress) {
            return address;
        }
    }

    private static int word(byte[] bytes, int at) {
        return ((bytes[at] & 0xff) << 8) | (bytes[at + 1] & 0xff);
    }
}
