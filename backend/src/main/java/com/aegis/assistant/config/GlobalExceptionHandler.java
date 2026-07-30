package com.aegis.assistant.config;

import cn.dev33.satoken.exception.NotLoginException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常处理器
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(NotLoginException.class)
    public Result<String> handleNotLoginException(NotLoginException e) {
        return Result.error(401, e.getMessage() != null ? e.getMessage() : "登录失效，请重新登录");
    }

    @ExceptionHandler(Exception.class)
    public Result<String> handleException(Exception e) {
        // 在生产环境中，建议使用日志框架(如Slf4j)记录错误日志
        e.printStackTrace();
        return Result.error(500, e.getMessage() != null ? e.getMessage() : "Internal Server Error");
    }
}
