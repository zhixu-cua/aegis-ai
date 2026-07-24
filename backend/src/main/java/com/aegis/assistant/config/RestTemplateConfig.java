package com.aegis.assistant.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
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
}
