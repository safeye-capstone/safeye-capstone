package com.safeye.backend.domain.alert.controller;

import com.safeye.backend.domain.alert.service.AlertSseService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
@RequestMapping("/api/alerts")
@RequiredArgsConstructor
public class AlertController {

    private final AlertSseService alertSseService;

    @GetMapping(value = "/subscribe", produces = "text/event-stream;charset=UTF-8")
    public SseEmitter subscribe() {
        return alertSseService.subscribe();
    }
} //end
