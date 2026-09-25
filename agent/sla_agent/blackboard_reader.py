"""Read the Blackboard section through a logged-in client (BlackboardClient or a test double)."""

from sla_contract.schema import BbCourse, Blackboard

from sla_agent.parsers.blackboard import (
    announcements_from,
    assignments_from,
    course_url,
    materials_from,
    select_current_courses,
    walk_contents,
)


def read_blackboard(client, registered):
    me = client.user_id
    memberships = client.api_all(f"/v1/users/{me}/courses?limit=100&expand=course")
    courses = [m["course"] for m in memberships if isinstance(m, dict) and isinstance(m.get("course"), dict)]

    result = []
    for course, code in select_current_courses(courses, registered):
        cid = course["id"]
        announcements = client.api_all(f"/v1/courses/{cid}/announcements?limit=100")
        columns = client.api_all(f"/v2/courses/{cid}/gradebook/columns?limit=100")
        grades = client.api_all(f"/v2/courses/{cid}/gradebook/users/{me}?limit=100")
        top = client.api_all(f"/v1/courses/{cid}/contents?limit=100")
        tree = walk_contents(top, lambda item_id: client.api_all(f"/v1/courses/{cid}/contents/{item_id}/children?limit=100"))
        result.append(BbCourse(
            bb_id=cid,
            course_code=code,
            name=(course.get("name") or code)[:255],
            url=course_url(cid),
            announcements=announcements_from(announcements, cid),
            assignments=assignments_from(columns, grades, cid),
            materials=materials_from(tree, cid),
        ))
    return Blackboard(courses=result)
