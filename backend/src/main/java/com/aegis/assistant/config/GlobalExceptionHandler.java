package com.aegis.assistant.config;

import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常处理器
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(Exception.class)
    public Result<String> handleException(Exception e) {
        // 在生产环境中，建议使用日志框架(如Slf4j)记录错误日志
        e.printStackTrace();
        return Result.error(500, e.getMessage() != null ? e.getMessage() : "Internal Server Error");
    }
}
