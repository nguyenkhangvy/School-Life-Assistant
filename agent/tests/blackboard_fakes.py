"""Hand-written Blackboard answers for tests. The login form copies the real one at
https://blackboard.hcmiu.edu.vn/webapps/login/ (checked 2026-09-26)."""

BB = "https://blackboard.hcmiu.edu.vn"
LOGIN_URL = f"{BB}/webapps/login/"
LOGOUT_URL = f"{BB}/webapps/login/?action=logout"
API = f"{BB}/learn/api/public"

LOGIN_FORM = """
<form action="/webapps/login/" method="POST" id="login-form" name="login">
  <input type="text" name="user_id" id="user_id" value="">
  <input type="password" name="password" id="password" value="">
  <input type="submit" value="Login" name="login" id="entry-login">
  <input type="hidden" name="action" value="login">
  <input type="hidden" name="new_loc" value="">
  <input type="hidden" name="blackboard.platform.security.NonceUtil.nonce" value="NONCE-123">
</form>"""

LOGIN_PAGE = f"<html><head><title>Blackboard Learn</title></head><body>{LOGIN_FORM}</body></html>"
LOGIN_FAILED = f"<html><body><div id='loginErrorMessage'>The username or password you typed is incorrect.</div>{LOGIN_FORM}</body></html>"
CAPTCHA_LOGIN_PAGE = LOGIN_PAGE.replace("</form>", '<div class="g-recaptcha"></div></form>')
HOME_PAGE = "<html><body><div id='globalNavPageNavArea'>My Institution</div></body></html>"
ME = {"id": "_77_1", "userName": "student", "studentId": "S1"}
