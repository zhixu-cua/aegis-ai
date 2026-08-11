package com.aegis.assistant.util;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
public class RedisStreamUtil {
    
    private static final Logger log = LoggerFactory.getLogger(RedisStreamUtil.class);
    private final StringRedisTemplate redisTemplate;
    
    public RedisStreamUtil(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }
    
    /**
     * 发布消息到 Redis Stream
     */
    public void publish(String streamKey, String message) {
        try {
            redisTemplate.opsForStream()
                .add(streamKey, java.util.Map.of("data", message));
            log.debug("消息发布成功: stream={}, message={}", streamKey, message);
        } catch (Exception e) {
            log.error("消息发布失败: {}", e.getMessage(), e);
        }
    }
}