package com.aegis.assistant.dto;

public class UpdateDatasourceDTO {
    private String name;
    private String sourceConfig;
    private String syncFrequency;
    private Integer sourceRank;

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getSourceConfig() { return sourceConfig; }
    public void setSourceConfig(String sourceConfig) { this.sourceConfig = sourceConfig; }
    public String getSyncFrequency() { return syncFrequency; }
    public void setSyncFrequency(String syncFrequency) { this.syncFrequency = syncFrequency; }
    public Integer getSourceRank() { return sourceRank; }
    public void setSourceRank(Integer sourceRank) { this.sourceRank = sourceRank; }
}