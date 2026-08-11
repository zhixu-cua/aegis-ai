package com.aegis.assistant.service;

import cn.dev33.satoken.stp.StpUtil;
import org.springframework.stereotype.Service;

@Service
public class SaTokenService {
    public String getCurrentTenantId() {
        // Dummy implementation since actual logic depends on your SaToken setup
        return StpUtil.getLoginIdAsString();
    }
}
