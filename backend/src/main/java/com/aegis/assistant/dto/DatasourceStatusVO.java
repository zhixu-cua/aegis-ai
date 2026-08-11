package com.aegis.assistant.dto;

import java.time.LocalDateTime;

public class DatasourceStatusVO {
    private Long id;
    private String name;
    private String status;
    private Integer totalDocCount;
    private LocalDateTime lastSyncAt;
    private String lastError;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Integer getTotalDocCount() { return totalDocCount; }
    public void setTotalDocCount(Integer totalDocCount) { this.totalDocCount = totalDocCount; }
    public LocalDateTime getLastSyncAt() { return lastSyncAt; }
    public void setLastSyncAt(LocalDateTime lastSyncAt) { this.lastSyncAt = lastSyncAt; }
    public String getLastError() { return lastError; }
    public void setLastError(String lastError) { this.lastError = lastError; }
}