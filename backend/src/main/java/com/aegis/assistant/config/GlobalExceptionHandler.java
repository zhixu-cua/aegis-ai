package com.aegis.assistant.config;

import cn.dev33.satoken.exception.NotLoginException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常处理器
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(NotLoginException.class)
    public ResponseEntity<?> handleNotLoginException(NotLoginException e, HttpServletRequest request, HttpServletResponse response) {
        String msg = e.getMessage() != null ? e.getMessage() : "登录失效，请重新登录";

        // 响应已提交（如 SSE 已开始推流），无法再写内容，直接返回 null，避免二次异常
        if (response.isCommitted()) {
            log.warn("响应已提交，无法返回登录失效信息: {}", msg);
            return null;
        }

        if (isSSE(request, response)) {
            return ResponseEntity.status(401)
                    .contentType(MediaType.TEXT_EVENT_STREAM)
                    .body("data: " + buildJsonError(401, msg) + "\n\n");
        }
        return ResponseEntity.status(401).body(Result.error(401, msg));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<?> handleException(Exception e, HttpServletRequest request, HttpServletResponse response) {
        // 替换 e.printStackTrace() 为 log.error，并记录完整堆栈
        log.error("全局异常捕获: ", e);

        // 响应已提交（例如 SSE 已开始推流或客户端已断开），此时无法再写任何内容；
        // 直接返回 null，避免抛 “No converter ... text/event-stream” 二次异常并级联到 /error
        if (response.isCommitted()) {
            log.warn("响应已提交，跳过异常信息写入: {}", e.getMessage());
            return null;
        }

        String msg = e.getMessage() != null ? e.getMessage() : "Internal Server Error";
        if (isSSE(request, response)) {
            return ResponseEntity.status(500)
                    .contentType(MediaType.TEXT_EVENT_STREAM)
                    .body("data: " + buildJsonError(500, msg) + "\n\n");
        }
        return ResponseEntity.status(500).body(Result.error(500, msg));
    }

    /**
     * 判断当前请求是否为 SSE (Server-Sent Events) 流式请求。
     * <p>前端 fetch 并未显式设置 Accept: text/event-stream，因此不能只依赖 Accept 头，
     * 需要同时判断请求 URI 与响应已提交的 Content-Type，避免误判后向 SSE 响应写入 JSON 对象。</p>
     */
    private boolean isSSE(HttpServletRequest request, HttpServletResponse response) {
        String accept = request.getHeader("Accept");
        if (accept != null && accept.contains("text/event-stream")) {
            return true;
        }
        String uri = request.getRequestURI();
        if (uri != null && uri.contains("/chat/stream")) {
            return true;
        }
        String contentType = response.getContentType();
        return contentType != null && contentType.contains("text/event-stream");
    }

    /**
     * 构建 SSE 格式的 JSON 错误信息（需转义双引号）
     */
    private String buildJsonError(int code, String msg) {
        String escaped = msg.replace("\"", "\\\"");
        return "{\"code\":" + code + ",\"msg\":\"" + escaped + "\",\"data\":null}";
    }
}
