package com.aegis.assistant.entity;

import jakarta.persistence.*;
import com.fasterxml.jackson.annotation.JsonFormat;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.util.Date;

@Entity
@Table(name = "assistant_audit_log")
public class AssistantAuditLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id")
    private Long userId;

    @Column(name = "action_type")
    private String actionType; 

    @Column(name = "request_summary")
    private String requestSummary;

    @Column(name = "response_summary")
    private String responseSummary;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "source_refs", columnDefinition = "jsonb")
    private String sourceRefs; // 映射为 PostgreSQL 的 jsonb

    @Column(name = "result_flag")
    private String resultFlag;

    @Column(name = "create_time")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
    private Date createTime;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getUserId() {
        return userId;
    }

    public void setUserId(Long userId) {
        this.userId = userId;
    }

    public String getActionType() {
        return actionType;
    }

    public void setActionType(String actionType) {
        this.actionType = actionType;
    }

    public String getRequestSummary() {
        return requestSummary;
    }

    public void setRequestSummary(String requestSummary) {
        this.requestSummary = requestSummary;
    }

    public String getResponseSummary() {
        return responseSummary;
    }

    public void setResponseSummary(String responseSummary) {
        this.responseSummary = responseSummary;
    }

    public String getSourceRefs() {
        return sourceRefs;
    }

    public void setSourceRefs(String sourceRefs) {
        this.sourceRefs = sourceRefs;
    }

    public String getResultFlag() {
        return resultFlag;
    }

    public void setResultFlag(String resultFlag) {
        this.resultFlag = resultFlag;
    }

    public Date getCreateTime() {
        return createTime;
    }

    public void setCreateTime(Date createTime) {
        this.createTime = createTime;
    }
}