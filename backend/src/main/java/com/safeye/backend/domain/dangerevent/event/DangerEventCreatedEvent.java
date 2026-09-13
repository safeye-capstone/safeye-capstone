package com.safeye.backend.domain.dangerevent.event;

import com.safeye.backend.domain.dangerevent.dto.response.DangerEventDto;

public record DangerEventCreatedEvent(DangerEventDto dangerEvent) {
}
