package vn.edu.hcmiu.sla.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import vn.edu.hcmiu.sla.core.Text;

/** The Profile page's fields (spec 5.4): the name and email with register's rules and messages. */
public class ProfileForm {

    @NotBlank(message = RegisterForm.REQUIRED)
    @Size(max = 100, message = "Field cannot be longer than 100 characters.")
    private String displayName = "";

    @NotBlank(message = RegisterForm.REQUIRED)
    @Email(regexp = "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", message = "Invalid email address.")
    @Size(max = 255, message = "Field cannot be longer than 255 characters.")
    private String email = "";

    /** Needed only when the email changes. */
    private String currentPassword = "";

    public String getDisplayName() {
        return displayName;
    }

    public void setDisplayName(String displayName) {
        this.displayName = displayName == null ? "" : Text.strip(displayName);
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = AppUserDetailsService.normalizeEmail(email);
    }

    public String getCurrentPassword() {
        return currentPassword;
    }

    public void setCurrentPassword(String currentPassword) {
        this.currentPassword = currentPassword == null ? "" : currentPassword;
    }
}
