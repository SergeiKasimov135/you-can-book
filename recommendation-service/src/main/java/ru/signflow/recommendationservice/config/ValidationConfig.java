package ru.signflow.recommendationservice.config;

import build.buf.protovalidate.Validator;
import build.buf.protovalidate.ValidatorFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ValidationConfig {

    @Bean
    public Validator protoValidator() {
        return ValidatorFactory.newBuilder().build();
    }
}
