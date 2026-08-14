package com.aegis.assistant.dto;

/**
 * @author Administrator
 * @date 2026/7/23 17:35
 * @description TODO
 */
public class LoginRequest {

    private String username;
    private String useraccount;
    private String password;

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getUseraccount() {
        return useraccount;
    }

    public void setUseraccount(String useraccount) {
        this.useraccount = useraccount;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }
}
