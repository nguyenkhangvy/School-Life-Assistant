package vn.edu.hcmiu.sla.school.model;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;

public interface SchoolMailPeriodRepository extends JpaRepository<SchoolMailPeriod, Integer> {

    /** A user's Periods from email, with their email, soonest first. */
    @Query("select p from SchoolMailPeriod p join fetch p.mail m where m.userId = :userId"
            + " order by p.firstDay, p.lastDay, p.fromTime")
    List<SchoolMailPeriod> findOfUser(Integer userId);

    @Modifying
    @Query("delete from SchoolMailPeriod p where p.mail.id in (select m.id from SchoolMail m where m.userId = :userId)")
    void deleteAllOfUser(Integer userId);
}
