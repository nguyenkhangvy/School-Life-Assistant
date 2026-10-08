package vn.edu.hcmiu.sla.school.model;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;

public interface SchoolMailDeadlineRepository extends JpaRepository<SchoolMailDeadline, Integer> {

    /** A user's deadlines from email, with their email, soonest first. */
    @Query("select d from SchoolMailDeadline d join fetch d.mail m where m.userId = :userId order by d.day, d.time")
    List<SchoolMailDeadline> findOfUser(Integer userId);

    @Modifying
    @Query("delete from SchoolMailDeadline d where d.mail.id in (select m.id from SchoolMail m where m.userId = :userId)")
    void deleteAllOfUser(Integer userId);
}
