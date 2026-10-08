package vn.edu.hcmiu.sla.school.model;

import java.time.LocalDate;
import java.util.Collection;
import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface SchoolMailAddedPeriodRepository extends JpaRepository<SchoolMailAddedPeriod, Integer> {

    /** A user's added Periods, soonest first. */
    List<SchoolMailAddedPeriod> findByUserIdOrderByFirstDayAscLastDayAscFromTimeAsc(Integer userId);

    /** A user's added Periods of these emails (one card's keys), soonest first. */
    List<SchoolMailAddedPeriod> findByUserIdAndMailKeyInOrderByFirstDayAscLastDayAscFromTimeAsc(Integer userId,
            Collection<String> mailKeys);

    /** A user's added Periods running on some day of [from, to], soonest first. */
    @Query("select p from SchoolMailAddedPeriod p where p.userId = :userId and p.firstDay <= :to and p.lastDay >= :from"
            + " order by p.firstDay, p.lastDay, p.fromTime")
    List<SchoolMailAddedPeriod> findOverlapping(Integer userId, LocalDate from, LocalDate to);
}
