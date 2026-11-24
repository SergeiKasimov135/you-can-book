package ru.signflow.recommendationservice.service;

import com.google.protobuf.Timestamp;
import org.junit.jupiter.api.Test;
import ru.signflow.recommendationservice.grpc.CategoryVisitStat;
import ru.signflow.recommendationservice.grpc.EventCandidate;
import ru.signflow.recommendationservice.grpc.GetRecommendationsRequest;
import ru.signflow.recommendationservice.grpc.Recommendation;

import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

class RecommendationEngineTest {

    @Test
    void shouldRankCandidatesAndApplyLimit() {
        RecommendationEngine engine = new RecommendationEngine();

        GetRecommendationsRequest request =
                GetRecommendationsRequest.newBuilder()
                        .addCategoryStats(CategoryVisitStat.newBuilder()
                                .setCategoryId(7)
                                .setVisitCount(3)
                                .build())
                        .addCategoryStats(CategoryVisitStat.newBuilder()
                                .setCategoryId(12)
                                .setVisitCount(1)
                                .build())
                        .addCandidates(event(1, 7, "2030-11-10T18:00:00Z"))
                        .addCandidates(event(3, 12, "2030-11-01T18:00:00Z"))
                        .addCandidates(event(4, 7, "2030-11-05T18:00:00Z"))
                        .addCandidates(event(2, 7, "2030-11-05T18:00:00Z"))
                        .setLimit(3)
                        .build();

        List<Recommendation> result = engine.recommend(request);

        assertEquals(
                List.of(2L, 4L, 1L),
                result.stream().map(Recommendation::getEventId).toList()
        );

        assertEquals(
                List.of(3L, 3L, 3L),
                result.stream().map(Recommendation::getScore).toList()
        );
    }

    private static EventCandidate event(
            long id,
            long categoryId,
            String startsAt
    ) {
        Instant instant = Instant.parse(startsAt);

        return EventCandidate.newBuilder()
                .setEventId(id)
                .addCategoryIds(categoryId)
                .setStartsAt(Timestamp.newBuilder()
                        .setSeconds(instant.getEpochSecond())
                        .setNanos(instant.getNano())
                        .build())
                .build();
    }
}