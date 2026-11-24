package ru.signflow.recommendationservice.service;

import org.springframework.stereotype.Service;
import ru.signflow.recommendationservice.grpc.CategoryVisitStat;
import ru.signflow.recommendationservice.grpc.EventCandidate;
import ru.signflow.recommendationservice.grpc.GetRecommendationsRequest;
import ru.signflow.recommendationservice.grpc.Recommendation;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class RecommendationEngine {

    private record ScoredEvent(EventCandidate eventCandidate, long score) {
    }

    private long calculateScore(EventCandidate eventCandidate, Map<Long, Integer> visitsByCategory) {
        long score = 0;

        Set<Long> categoryIds = new HashSet<>(eventCandidate.getCategoryIdsList());
        for (long categoryId : categoryIds) {
            int visits = visitsByCategory.getOrDefault(categoryId, 0);
            score += visits;
        }

        return score;
    }

    public List<Recommendation> recommend(GetRecommendationsRequest request) {
        if (request.getLimit() <= 0) {
            throw new IllegalArgumentException("Limit must be greater than zero");
        }

        Map<Long, Integer> visitsByCategory = new HashMap<>();
        for (CategoryVisitStat stat : request.getCategoryStatsList()) {
            visitsByCategory.put(stat.getCategoryId(), stat.getVisitCount());
        }

        List<ScoredEvent> scoredEvents = new ArrayList<>();
        for (EventCandidate candidate : request.getCandidatesList()) {
            scoredEvents.add(new ScoredEvent(
                    candidate, calculateScore(candidate, visitsByCategory))
            );
        }

        Comparator<ScoredEvent> ranking = Comparator
                .comparingLong(ScoredEvent::score)
                .reversed()
                .thenComparingLong(
                        item -> item.eventCandidate().getStartsAt().getSeconds()
                )
                .thenComparingInt(
                        item -> item.eventCandidate().getStartsAt().getNanos()
                )
                .thenComparingLong(
                        item -> item.eventCandidate().getEventId()
                );
        scoredEvents.sort(ranking);

        int resultSize = Math.min(request.getLimit(), scoredEvents.size());
        List<Recommendation> recommendations = new ArrayList<>(resultSize);

        for (int i = 0; i < resultSize; ++i) {
            ScoredEvent item = scoredEvents.get(i);

            recommendations.add(Recommendation.newBuilder()
                    .setEventId(item.eventCandidate().getEventId())
                    .setScore(item.score())
                    .build());
        }

        return recommendations;
    }
}
