package com.aegis.assistant.task;

import com.aegis.assistant.entity.KbDatasource;
import com.aegis.assistant.repository.KbDatasourceRepository;
import com.aegis.assistant.service.KnowledgeBaseService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

@Component
public class DatasourceSyncTask {

    private static final Logger log = LoggerFactory.getLogger(DatasourceSyncTask.class);

    private final KbDatasourceRepository datasourceRepository;
    private final KnowledgeBaseService knowledgeBaseService;

    public DatasourceSyncTask(KbDatasourceRepository datasourceRepository, KnowledgeBaseService knowledgeBaseService) {
        this.datasourceRepository = datasourceRepository;
        this.knowledgeBaseService = knowledgeBaseService;
    }

    // 每小时执行一次
    @Scheduled(cron = "0 0 * * * ?")
    public void syncHourly() {
        log.info("开始执行每小时同步任务");
        List<KbDatasource> datasources = datasourceRepository.findByStatusAndSyncFrequency("active", "hourly");
        for (KbDatasource ds : datasources) {
            triggerSync(ds);
        }
    }

    // 每天凌晨2点执行一次
    @Scheduled(cron = "0 0 2 * * ?")
    public void syncDaily() {
        log.info("开始执行每日同步任务");
        List<KbDatasource> datasources = datasourceRepository.findByStatusAndSyncFrequency("active", "daily");
        for (KbDatasource ds : datasources) {
            triggerSync(ds);
        }
    }

    private void triggerSync(KbDatasource ds) {
        try {
            String path = "";
            if ("local".equals(ds.getSourceType())) {
                Map<String, Object> config = ds.getSourceConfig();
                if (config != null && config.containsKey("path")) {
                    path = String.valueOf(config.get("path"));
                }
            } else if ("cos".equals(ds.getSourceType())) {
                Map<String, Object> config = ds.getSourceConfig();
                if (config != null && config.containsKey("prefix")) {
                    path = String.valueOf(config.get("prefix"));
                }
                if (path == null || path.isEmpty()) {
                    path = "/";
                }
            }
            if (!path.isEmpty()) {
                knowledgeBaseService.forceRefresh(ds.getId(), path);
                log.info("自动同步触发成功: 数据源ID={}, 路径={}", ds.getId(), path);
            }
        } catch (Exception e) {
            log.error("自动同步触发失败: 数据源ID={}", ds.getId(), e);
        }
    }
}
