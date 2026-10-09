package vn.edu.hcmiu.sla.auth;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface UserRepository extends JpaRepository<User, Integer> {

    Optional<User> findByEmail(String email);

    boolean existsByEmail(String email);

    /** Is there an active account with this role ("admin")? */
    boolean existsByRoleAndDeactivatedAtIsNull(String role);
}
