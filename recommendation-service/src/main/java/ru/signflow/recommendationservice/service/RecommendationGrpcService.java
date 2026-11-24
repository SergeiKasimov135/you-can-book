package ru.signflow.recommendationservice.service;

import build.buf.protovalidate.ValidationResult;
import build.buf.protovalidate.Validator;
import build.buf.protovalidate.exceptions.ValidationException;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import ru.signflow.recommendationservice.grpc.GetRecommendationsRequest;
import ru.signflow.recommendationservice.grpc.GetRecommendationsResponse;
import ru.signflow.recommendationservice.grpc.RecommendationServiceGrpc;

@Service
public class RecommendationGrpcService extends RecommendationServiceGrpc.RecommendationServiceImplBase {

    private static final Logger log = LoggerFactory.getLogger(RecommendationGrpcService.class);

    private final RecommendationEngine engine;
    private final Validator validator;

    public RecommendationGrpcService(RecommendationEngine engine, Validator validator) {
        this.engine = engine;
        this.validator = validator;
    }

    @Override
    public void getRecommendations(GetRecommendationsRequest request,
                                   StreamObserver<GetRecommendationsResponse> responseObserver) {
        ValidationResult requestValidation;
        try {
            requestValidation = validator.validate(request);
        } catch (ValidationException | RuntimeException e) {
            log.error("Failed to validate recommendation request", e);
            responseObserver.onError(Status.INTERNAL
                    .withDescription("Failed to validate recommendation request")
                    .asRuntimeException());
            return;
        }

        if (!requestValidation.isSuccess()) {
            responseObserver.onError(Status.INVALID_ARGUMENT
                    .withDescription(requestValidation.toString())
                    .asRuntimeException());
            return;
        }

        GetRecommendationsResponse response;
        try {
            response = GetRecommendationsResponse.newBuilder()
                    .addAllRecommendations(engine.recommend(request))
                    .build();

            ValidationResult responseValidation = validator.validate(response);
            if (!responseValidation.isSuccess()) {
                throw new IllegalStateException("Generated invalid recommendations: " + responseValidation);
            }
        } catch (ValidationException | RuntimeException e) {
            log.error("Failed to calculate recommendations", e);
            responseObserver.onError(Status.INTERNAL
                    .withDescription("Failed to calculate recommendations")
                    .asRuntimeException());
            return;
        }

        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }
}
