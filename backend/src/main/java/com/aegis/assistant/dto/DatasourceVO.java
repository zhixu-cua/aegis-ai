package com.aegis.assistant.dto;

import java.time.LocalDateTime;

public class DatasourceVO {
    private Long id;
    private String name;
    private String sourceType;
    private String status;
    private Integer totalDocCount;
    private LocalDateTime lastSyncAt;
    private Boolean isShared;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getSourceType() { return sourceType; }
    public void setSourceType(String sourceType) { this.sourceType = sourceType; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Integer getTotalDocCount() { return totalDocCount; }
    public void setTotalDocCount(Integer totalDocCount) { this.totalDocCount = totalDocCount; }
    public LocalDateTime getLastSyncAt() { return lastSyncAt; }
    public void setLastSyncAt(LocalDateTime lastSyncAt) { this.lastSyncAt = lastSyncAt; }
    public Boolean getIsShared() { return isShared; }
    public void setIsShared(Boolean isShared) { this.isShared = isShared; }
}