package com.aegis.assistant.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class SaTokenConfigure implements WebMvcConfigurer {

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        // 注册 Sa-Token 登录校验拦截器。
        // 使用 SaTokenAuthInterceptor 包装：只在 REQUEST 分发时鉴权，跳过 ASYNC/ERROR 二次分发，
        // 避免 SSE 流式接口异步完成后抛 “SaTokenContext 上下文尚未初始化” 异常。
        registry.addInterceptor(new SaTokenAuthInterceptor())
                .addPathPatterns("/**")
                .excludePathPatterns("/error");
    }
}
