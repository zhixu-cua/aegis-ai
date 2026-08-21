package com.aegis.assistant.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.web.client.RestTemplate;

@Configuration
public class RestTemplateConfig {

    @Bean
    public RestTemplate restTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setReadTimeout(120000); // 读取超时设为120秒，适应大模型推理时间
        factory.setConnectTimeout(10000); // 连接超时设为10秒
        return new RestTemplate(factory);
    }

    /**
     * SSE 流式推流专用线程池。
     * 避免 ChatService.chatStream 每次请求都 new Thread()，导致线程无界增长、
     * 长时间运行后资源耗尽的问题。
     */
    @Bean
    public ThreadPoolTaskExecutor streamTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(50);
        executor.setQueueCapacity(200);
        executor.setThreadNamePrefix("sse-stream-");
        // 应用关闭时不等待任务完成，避免阻塞关闭
        executor.setWaitForTasksToCompleteOnShutdown(false);
        executor.setAwaitTerminationSeconds(10);
        executor.initialize();
        return executor;
    }
}
