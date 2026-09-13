package com.safeye.backend.domain.alert.service;

import com.safeye.backend.domain.dangerevent.dto.response.DangerEventDto;
import com.safeye.backend.domain.dangerevent.event.DangerEventCreatedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

@Service
public class AlertSseService {

    private static final long TIMEOUT = 60L * 60 * 1000;

    private final List<SseEmitter> emitters = new CopyOnWriteArrayList<>();

    public SseEmitter subscribe() {
        SseEmitter emitter = new SseEmitter(TIMEOUT);

        emitters.add(emitter);
        emitter.onCompletion(() -> emitters.remove(emitter));
        emitter.onTimeout(() -> emitters.remove(emitter));
        emitter.onError(e -> emitters.remove(emitter));

        try {
            emitter.send(SseEmitter.event().name("connected").data("ok"));
        } catch (IOException e) {
            emitters.remove(emitter);
        }

        return emitter;
    }

    public void broadcast(DangerEventDto dto) {
        for (SseEmitter emitter : emitters) {
            try {
                emitter.send(SseEmitter.event().name("danger").data(dto));
            } catch (IOException e) {
                emitters.remove(emitter);
            }
        }
    }

    @EventListener
    public void onDangerEventCreated(DangerEventCreatedEvent event) {
        broadcast(event.dangerEvent());
    }

} //end
