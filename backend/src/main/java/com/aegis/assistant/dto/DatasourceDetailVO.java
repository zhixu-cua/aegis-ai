package com.aegis.assistant.dto;

import java.time.LocalDateTime;

public class DatasourceDetailVO {
    private Long id;
    private String name;
    private String sourceType;
    private java.util.Map<String, Object> sourceConfig;
    private String syncFrequency;
    private Integer sourceRank;
    private String status;
    private Integer totalDocCount;
    private LocalDateTime lastSyncAt;
    private String lastError;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getSourceType() { return sourceType; }
    public void setSourceType(String sourceType) { this.sourceType = sourceType; }
    public java.util.Map<String, Object> getSourceConfig() { return sourceConfig; }
    public void setSourceConfig(java.util.Map<String, Object> sourceConfig) { this.sourceConfig = sourceConfig; }
    public String getSyncFrequency() { return syncFrequency; }
    public void setSyncFrequency(String syncFrequency) { this.syncFrequency = syncFrequency; }
    public Integer getSourceRank() { return sourceRank; }
    public void setSourceRank(Integer sourceRank) { this.sourceRank = sourceRank; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Integer getTotalDocCount() { return totalDocCount; }
    public void setTotalDocCount(Integer totalDocCount) { this.totalDocCount = totalDocCount; }
    public LocalDateTime getLastSyncAt() { return lastSyncAt; }
    public void setLastSyncAt(LocalDateTime lastSyncAt) { this.lastSyncAt = lastSyncAt; }
    public String getLastError() { return lastError; }
    public void setLastError(String lastError) { this.lastError = lastError; }
}