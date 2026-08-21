package com.aegis.assistant.config;

import cn.dev33.satoken.interceptor.SaInterceptor;
import cn.dev33.satoken.router.SaRouter;
import cn.dev33.satoken.stp.StpUtil;
import jakarta.servlet.DispatcherType;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * Sa-Token 登录校验拦截器（带异步/错误分发保护）。
 *
 * <p>背景：SSE 流式接口（/assistant/chat/stream）使用 SseEmitter 异步处理。当流正常结束或出错时，
 * Tomcat 会以 {@link DispatcherType#ASYNC} / {@link DispatcherType#ERROR} 再次分发请求；此时
 * Sa-Token 的上下文过滤器（SaTokenContextFilterForJakartaServlet）不会再次执行，ThreadLocal 中的
 * 请求上下文已经被清空，若继续调用 SaRouter.match()，会抛出
 * “SaTokenContext 上下文尚未初始化” 异常，并进一步触发 /error 错误页的级联报错。</p>
 *
 * <p>首次 REQUEST 分发时已经完成鉴权，异步/错误分发只是同一请求的二次进入，无需重复校验，直接放行。</p>
 */
public class SaTokenAuthInterceptor implements HandlerInterceptor {

    private final SaInterceptor delegate = new SaInterceptor(handle ->
            SaRouter.match("/api/**", "/user/**", "/assistant/**")
                    .notMatch("/user/doLogin", "/user/doRegister", "/api/internal/**")
                    .check(r -> StpUtil.checkLogin()));

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        // 只在最初的 REQUEST 分发时鉴权，跳过 ASYNC / ERROR / FORWARD / INCLUDE 二次分发，
        // 避免在 Sa-Token 上下文未初始化的线程上调用 SaRouter 导致异常。
        if (request.getDispatcherType() != DispatcherType.REQUEST) {
            return true;
        }
        return delegate.preHandle(request, response, handler);
    }
}
