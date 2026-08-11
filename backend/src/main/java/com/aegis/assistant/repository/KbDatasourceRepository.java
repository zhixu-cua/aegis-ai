package com.aegis.assistant.repository;

import com.aegis.assistant.entity.KbDatasource;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface KbDatasourceRepository extends JpaRepository<KbDatasource, Long> {
    List<KbDatasource> findByTenantId(String tenantId);
    List<KbDatasource> findByStatusAndSyncFrequency(String status, String syncFrequency);
}
