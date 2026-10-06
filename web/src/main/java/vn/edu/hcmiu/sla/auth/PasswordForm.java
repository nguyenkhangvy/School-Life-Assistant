package vn.edu.hcmiu.sla.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** The Password page's fields (spec 5.5). Passwords are kept exactly as typed, as on register. */
public class PasswordForm {

    private String currentPassword = "";

    @Size(min = 8, max = 128, message = "Field must be between 8 and 128 characters long.")
    private String password = "";

    @NotBlank(message = RegisterForm.REQUIRED)
    private String confirm = "";

    public String getCurrentPassword() {
        return currentPassword;
    }

    public void setCurrentPassword(String currentPassword) {
        this.currentPassword = currentPassword == null ? "" : currentPassword;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password == null ? "" : password;
    }

    public String getConfirm() {
        return confirm;
    }

    public void setConfirm(String confirm) {
        this.confirm = confirm == null ? "" : confirm;
    }
}
